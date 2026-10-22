import re
import uuid
from dataclasses import dataclass

from langgraph.types import interrupt

from src.configs.logger import get_logger
from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.graph.state import BlogState
from src.modules.agent.nodes.base import emit, workflow_node
from src.modules.agent.nodes.llm import invoke_structured
from src.modules.agent.ports.output.model_factory import ModelRole
from src.modules.agent.prompts.context_files import render_contract
from src.modules.agent.prompts.writing import (
    PROMPT_VERSION,
    judge_messages,
    metadata_messages,
    outline_messages,
    section_messages,
)
from src.modules.agent.schemas.writing import (
    JudgeReportOut,
    MetadataOut,
    OutlineOut,
    SectionDraftOut,
    normalize_judge,
    normalize_metadata,
    normalize_outline,
)
from src.modules.articles.domain.content_hash import compute_content_hash
from src.modules.articles.domain.markdown_tools import assemble_article, strip_heading_number, tidy_markdown
from src.modules.articles.domain.validators import ValidationContext, has_blockers, validate_article
from src.modules.research.infrastructure.adapters.url_tools import canonicalize_url
from src.modules.shared.domain.entities import (
    ArticleDraftEntity,
    ArticleMetadata,
    ArticleRevisionEntity,
    DraftSection,
    EvaluationResultEntity,
    IssueSeverity,
    ResearchClaimEntity,
    ResearchSourceEntity,
    RevisionAuthor,
    SourceStatus,
    ValidationIssue,
)
from src.modules.shared.domain.value_objects import TaskStatus

logger = get_logger(__name__)

USABLE = (SourceStatus.ASSESSED, SourceStatus.LOW_QUALITY)


def _task_id(state: BlogState) -> uuid.UUID:
    return uuid.UUID(state["task_id"])


@dataclass
class Evidence:
    """Claims usable for writing, with short refs (C1..) for prompts and a way back to ids/URLs."""

    claims: list[ResearchClaimEntity]
    sources: dict[uuid.UUID, ResearchSourceEntity]
    ref_of: dict[uuid.UUID, str]
    claim_of: dict[str, ResearchClaimEntity]

    def lines(self, claim_ids: list[str] | None = None, limit: int = 80) -> str:
        wanted = set(claim_ids) if claim_ids is not None else None
        rows = []
        for claim in self.claims:
            if wanted is not None and str(claim.id) not in wanted:
                continue
            source = self.sources[claim.source_id]
            quality = f"{source.quality_score:.2f}" if source.quality_score is not None else "?"
            flag = "" if claim.quote_verified else " [unverified quote]"
            low = " [low-quality source]" if source.status == SourceStatus.LOW_QUALITY else ""
            rows.append(
                f"- {self.ref_of[claim.id]}: {claim.text} — source: [{source.title or source.publisher or 'source'}]"
                f"({source.canonical_url}) ({source.source_type or 'other'}, quality {quality}){flag}{low}"
            )
            if len(rows) >= limit:
                break
        return "\n".join(rows)

    def ids_for(self, refs: list[str]) -> list[str]:
        return [str(self.claim_of[r.strip()].id) for r in refs if r.strip() in self.claim_of]

    def source_urls(self) -> set[str]:
        urls = set()
        for source in self.sources.values():
            urls.update({source.url, source.canonical_url})
        return urls


class WritingNodes:
    def __init__(self, deps: WorkflowDeps):
        self.deps = deps

    # --- shared helpers -----------------------------------------------------------------------

    async def _evidence(self, task_id: uuid.UUID) -> Evidence:
        sources = {s.id: s for s in await self.deps.store.list_sources(task_id) if s.status in USABLE}
        claims = sorted(
            (c for c in await self.deps.store.list_claims(task_id) if c.source_id in sources),
            key=lambda c: (sources[c.source_id].status != SourceStatus.ASSESSED, -(sources[c.source_id].quality_score or 0), not c.quote_verified),
        )[: self.deps.settings.draft_evidence_claims]
        ref_of = {claim.id: f"C{index}" for index, claim in enumerate(claims, start=1)}
        return Evidence(claims, sources, ref_of, {ref_of[claim.id]: claim for claim in claims})

    async def _style(self) -> tuple[str, str, str, str]:
        style_version, style = await self.deps.store.style_guide()
        contract_version, contract = render_contract()
        return style_version, style, contract_version, contract

    @staticmethod
    def _outline_overview(outline: dict) -> str:
        return "\n".join(f"- {s['heading']}: {s['goal']}" for s in outline["sections"])

    @staticmethod
    def _section_brief(spec: dict) -> str:
        points = "\n".join(f"  - {p}" for p in spec.get("key_points", []))
        needs = ", ".join(spec.get("needs", [])) or "none"
        return f"Goal: {spec.get('goal', '')}\nKey points:\n{points}\nInclude: {needs}\nTarget length: ~{spec.get('est_words', 300)} words"

    @staticmethod
    def _clean_section(markdown: str, heading: str | None) -> str:
        lines = markdown.strip().split("\n")
        own = strip_heading_number(heading or "").lower()
        # Models sometimes repeat the section heading (as H1/H2, or as an H3 copy) despite instructions.
        while lines and (
            lines[0].lstrip().startswith(("# ", "## "))
            or (own and lines[0].lstrip().startswith("### ") and strip_heading_number(lines[0].lstrip()[4:]).lower() == own)
            or not lines[0].strip()
        ):
            lines = lines[1:]
        return tidy_markdown("\n".join(lines))

    def _references(self, sections: list[DraftSection], evidence: Evidence) -> list[dict]:
        text = "\n".join(s.markdown for s in sections)
        by_url = {}
        for source in evidence.sources.values():
            by_url[canonicalize_url(source.url)] = source
            by_url[canonicalize_url(source.canonical_url)] = source
        cited: list[ResearchSourceEntity] = []
        for url in re.findall(r"\]\((https?://[^)\s]+)\)", text):
            source = by_url.get(canonicalize_url(url))
            if source is not None and source not in cited:
                cited.append(source)
        return [{"title": s.title, "url": s.canonical_url, "publisher": s.publisher} for s in cited]

    async def _write_section(
        self, task, outline: dict, spec: dict | None, evidence: Evidence, previous_tail: str, style: str, contract: str,
        current: str | None = None, feedback: str | None = None,
    ) -> SectionDraftOut:
        heading = None if spec is None else spec["heading"]
        brief = f"Goal: {outline['intro_goal']}" if spec is None else self._section_brief(spec)
        claim_ids = None if spec is None or not spec.get("claim_ids") else spec["claim_ids"]
        messages = section_messages(
            task,
            title=outline["title"],
            angle=outline["angle"],
            outline_overview=self._outline_overview(outline),
            section_heading=heading,
            section_brief=brief,
            evidence=evidence.lines(claim_ids, limit=25 if claim_ids else 12),
            previous_tail=previous_tail,
            style_guide=style,
            render_contract=contract,
            current_markdown=current,
            feedback=feedback,
        )
        return await invoke_structured(self.deps.models.get(ModelRole.WRITER), SectionDraftOut, messages)

    def _claim_map(self, out: SectionDraftOut, evidence: Evidence) -> list[dict]:
        return [
            {"sentence": entry.sentence[:300], "claim_ids": evidence.ids_for(entry.claim_refs), "support": entry.support}
            for entry in out.claim_map[:40]
        ]

    async def _assemble(self, draft: ArticleDraftEntity, evidence: Evidence) -> None:
        title = draft.metadata.title if draft.metadata else "Untitled"
        draft.markdown = assemble_article(title, draft.sections, self._references(draft.sections, evidence))

    # --- outline ------------------------------------------------------------------------------

    @workflow_node("outline", TaskStatus.OUTLINING, timeout_seconds=600)
    async def outline(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        brief = await self.deps.store.get_brief(task_id)
        evidence = await self._evidence(task_id)
        _, style, _, _ = await self._style()
        plan = task.research_plan or {}
        must_cover = [*plan.get("must_cover", [])]
        settings = self.deps.settings

        feedback = None
        for _attempt in range(2):
            out = await invoke_structured(
                self.deps.models.get(ModelRole.PLANNER),
                OutlineOut,
                outline_messages(
                    task,
                    (brief.data.get("summary", "") if brief else ""),
                    evidence.lines(),
                    must_cover,
                    style,
                    settings.draft_max_sections,
                    feedback,
                ),
            )
            out = normalize_outline(out, settings.draft_max_sections)
            covered = {m.requirement for m in out.requirement_map}
            missing = [r for r in must_cover if r not in covered]
            if out.sections and not missing:
                break
            feedback = (
                ("No sections were planned. " if not out.sections else "")
                + (f"These requirements are not mapped to any section: {missing}" if missing else "")
            )
        if not out.sections:
            raise ValueError("The outline has no sections")

        outline = {
            "title": out.title_options[0],
            "title_options": out.title_options,
            "angle": task.angle or out.angle,
            "intro_goal": out.intro_goal,
            "next_steps": out.next_steps,
            "must_cover": must_cover,
            "covered_requirements": sorted({m.requirement for m in out.requirement_map}),
            "sections": [
                {
                    "key": f"s{index}",
                    "heading": strip_heading_number(section.heading),
                    # "Step N:" headings only make sense in tutorials.
                    "heading_style": section.heading_style if str(task.format) == "tutorial" or section.heading_style != "step" else "numbered",
                    "goal": section.goal,
                    "key_points": section.key_points,
                    "claim_ids": evidence.ids_for(section.claim_refs),
                    "needs": list(section.needs),
                    "est_words": section.est_words,
                }
                for index, section in enumerate(out.sections, start=1)
            ],
        }
        await self.deps.store.update_task(task_id, outline=outline, angle=outline["angle"])
        emit("outline_ready", sections=len(outline["sections"]), title=outline["title"])
        return {"outline": outline, "review_outline": task.review_outline}

    @staticmethod
    def route_after_outline(state: BlogState) -> str:
        return "review_outline" if state.get("review_outline") else "draft_article"

    @workflow_node("review_outline", None)
    async def review_outline(self, state: BlogState) -> dict:
        # Optional owner check before drafting; POST /tasks/{id}/outline/approve resumes it.
        decision = interrupt({"type": "outline_review", "task_id": state["task_id"]}) or {}
        edited = decision.get("outline") if isinstance(decision, dict) else None
        if edited:
            outline = {**state["outline"], **{k: v for k, v in edited.items() if k in ("title", "angle", "intro_goal", "sections")}}
            await self.deps.store.update_task(_task_id(state), outline=outline)
            return {"outline": outline}
        return {}

    # --- draft --------------------------------------------------------------------------------

    @workflow_node("draft_article", TaskStatus.DRAFTING, timeout_seconds=1800)
    async def draft_article(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        outline = state["outline"]
        evidence = await self._evidence(task_id)
        _, style, _, contract = await self._style()

        # Resume-friendly: a retry after a crash keeps sections that were already written.
        existing = await self.deps.store.get_draft(task_id)
        done = {s.key: s for s in (existing.sections if existing else []) if s.markdown}
        specs = [("intro", None)] + [(spec["key"], spec) for spec in outline["sections"]]
        draft = ArticleDraftEntity(task_id=task_id, sections=[])
        previous_tail = ""
        for key, spec in specs:
            if key in done:
                section = done[key]
            else:
                out = await self._write_section(task, outline, spec, evidence, previous_tail, style, contract)
                section = DraftSection(
                    key=key,
                    heading=None if spec is None else spec["heading"],
                    heading_style="plain" if spec is None else spec["heading_style"],
                    goal=outline["intro_goal"] if spec is None else spec["goal"],
                    markdown=self._clean_section(out.markdown, None if spec is None else spec["heading"]),
                    claim_map=self._claim_map(out, evidence),
                )
                emit("section_drafted", key=key, heading=section.heading or "Introduction", words=len(section.markdown.split()))
            draft.sections.append(section)
            previous_tail = section.markdown[-600:]
            await self.deps.store.save_draft(draft)

        meta = await invoke_structured(
            self.deps.models.get(ModelRole.FAST),
            MetadataOut,
            metadata_messages(task, outline["title_options"], outline["angle"], draft.sections[0].markdown),
        )
        draft.metadata = await self._unique_metadata(normalize_metadata(meta, meta.title.strip() or outline["title"]), task_id)
        await self._assemble(draft, evidence)
        await self.deps.store.save_draft(draft)
        emit("draft_assembled", words=len(draft.markdown.split()), title=draft.metadata.title)
        return {}

    async def _unique_metadata(self, meta: MetadataOut, task_id: uuid.UUID) -> ArticleMetadata:
        slug, suffix = meta.slug, 2
        while await self.deps.store.slug_taken(slug, task_id):
            slug = f"{meta.slug[:76]}-{suffix}"
            suffix += 1
        return ArticleMetadata(title=meta.title, slug=slug, description=meta.description, tags=meta.tags)

    # --- validate + judge ---------------------------------------------------------------------

    @workflow_node("validate_draft", TaskStatus.VALIDATING, timeout_seconds=120)
    async def validate_draft(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        draft = await self.deps.store.get_draft(task_id)
        evidence = await self._evidence(task_id)
        outline = state["outline"]
        issues = validate_article(
            draft.markdown,
            ValidationContext(
                format=str(task.format),
                metadata=draft.metadata,
                source_urls=evidence.source_urls(),
                must_cover=outline.get("must_cover", []),
                covered_requirements=set(outline.get("covered_requirements", [])),
                expected_words=sum(s["est_words"] for s in outline["sections"]) + 250,
            ),
        )
        draft.issues = issues
        await self.deps.store.save_draft(draft)
        emit(
            "validation_done",
            blockers=sum(i.severity == IssueSeverity.BLOCKER for i in issues),
            warnings=sum(i.severity == IssueSeverity.WARNING for i in issues),
        )
        return {}

    @workflow_node("judge_draft", TaskStatus.VALIDATING, timeout_seconds=600)
    async def judge_draft(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        draft = await self.deps.store.get_draft(task_id)
        evidence = await self._evidence(task_id)
        _, style, _, _ = await self._style()
        report = normalize_judge(
            await invoke_structured(
                self.deps.models.get(ModelRole.JUDGE),
                JudgeReportOut,
                judge_messages(task, draft.markdown, evidence.lines(), state["outline"].get("must_cover", []), style),
            )
        )
        draft.judge = report.model_dump()
        await self.deps.store.save_draft(draft)

        min_score = self.deps.settings.draft_min_judge_score
        needs_revision = (
            has_blockers(draft.issues)
            or any(i.severity == "blocker" for i in report.issues)
            or min(report.scores.model_dump().values()) < min_score
        )
        can_revise = draft.self_revisions < self.deps.settings.draft_max_self_revisions
        emit("judge_done", scores=report.scores.model_dump(), needs_revision=needs_revision, will_revise=needs_revision and can_revise)
        return {"needs_revision": needs_revision and can_revise}

    @staticmethod
    def route_after_judge(state: BlogState) -> str:
        return "self_revise" if state.get("needs_revision") else "save_revision"

    # --- bounded self-revision ----------------------------------------------------------------

    def _issues_by_section(self, draft: ArticleDraftEntity) -> tuple[dict[str, list[str]], bool]:
        names = {}
        for section in draft.sections:
            if section.heading:
                names[strip_heading_number(section.heading).lower()] = section.key
        grouped: dict[str, list[str]] = {}
        metadata_issue = False

        def add(section_name: str | None, text: str) -> None:
            key = names.get(strip_heading_number(section_name or "").lower())
            if key:
                grouped.setdefault(key, []).append(text)

        for issue in draft.issues:
            if issue.severity == IssueSeverity.INFO:
                continue
            if issue.rule.startswith("META_"):
                metadata_issue = True
            add(issue.section, f"[{issue.severity}] {issue.message}")
        for issue in (draft.judge or {}).get("issues", []):
            if issue["severity"] != "info":
                add(issue.get("section"), f"[{issue['severity']}] {issue['problem']} Fix: {issue['suggested_fix']}")
        return grouped, metadata_issue

    @workflow_node("self_revise", TaskStatus.DRAFTING, timeout_seconds=1200)
    async def self_revise(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        draft = await self.deps.store.get_draft(task_id)
        outline = state["outline"]
        evidence = await self._evidence(task_id)
        _, style, _, contract = await self._style()
        specs = {spec["key"]: spec for spec in outline["sections"]}
        grouped, metadata_issue = self._issues_by_section(draft)

        revised = []
        for index, section in enumerate(draft.sections):
            problems = grouped.get(section.key)
            if not problems:
                continue  # untouched sections stay byte-identical
            previous_tail = draft.sections[index - 1].markdown[-600:] if index else ""
            out = await self._write_section(
                task, outline, specs.get(section.key), evidence, previous_tail, style, contract,
                current=section.markdown, feedback="\n".join(f"- {p}" for p in problems[:12]),
            )
            section.markdown = self._clean_section(out.markdown, section.heading)
            section.claim_map = self._claim_map(out, evidence)
            section.revisions += 1
            revised.append(section.key)
        if metadata_issue and draft.metadata:
            fixed = normalize_metadata(
                MetadataOut(**draft.metadata.model_dump()), draft.metadata.title.strip() or outline["title"]
            )
            draft.metadata = await self._unique_metadata(fixed, task_id)

        draft.history.append(
            {
                "round": draft.self_revisions + 1,
                "revised_sections": revised,
                "blockers": sum(i.severity == IssueSeverity.BLOCKER for i in draft.issues),
                "scores": (draft.judge or {}).get("scores"),
            }
        )
        draft.self_revisions += 1
        await self._assemble(draft, evidence)
        await self.deps.store.save_draft(draft)
        emit("self_revision", round=draft.self_revisions, sections=revised)
        return {}

    # --- persist + pause for review -----------------------------------------------------------

    @workflow_node("save_revision", TaskStatus.VALIDATING, timeout_seconds=120)
    async def save_revision(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        draft = await self.deps.store.get_draft(task_id)
        meta = draft.metadata
        style_version, _, contract_version, _ = await self._style()
        previous = await self.deps.store.latest_revision(task_id)
        judge = draft.judge or {}

        revision = ArticleRevisionEntity(
            task_id=task_id,
            revision_number=(previous.revision_number + 1) if previous else 1,
            parent_revision_id=previous.id if previous else None,
            title=meta.title,
            slug=meta.slug,
            description=meta.description,
            tags=meta.tags,
            markdown=draft.markdown,
            created_by=RevisionAuthor.AI,
            content_hash=compute_content_hash(
                title=meta.title, slug=meta.slug, description=meta.description, tags=meta.tags, markdown=draft.markdown
            ),
            metadata={
                "outline": state["outline"],
                "claim_map": {s.key: s.claim_map for s in draft.sections},
                "unsupported_statements": judge.get("unsupported_statements", []),
                "self_revisions": draft.self_revisions,
                "history": draft.history,
                "style_guide_version": style_version,
                "render_contract_version": contract_version,
                "prompt_version": PROMPT_VERSION,
                "models": self.deps.models.describe(),
                "word_count": len(draft.markdown.split()),
            },
        )
        judge_issues = [
            ValidationIssue(rule="JUDGE", severity=i["severity"], message=f"{i['problem']} — {i['suggested_fix']}", section=i.get("section"), source="judge")
            for i in judge.get("issues", [])
        ]
        evaluations = [
            EvaluationResultEntity(
                revision_id=uuid.UUID(int=0), kind="deterministic", passed=not has_blockers(draft.issues), issues=draft.issues
            ),
            EvaluationResultEntity(
                revision_id=uuid.UUID(int=0),
                kind="judge",
                passed=bool(judge) and not any(i.severity == IssueSeverity.BLOCKER for i in judge_issues)
                and min((judge.get("scores") or {"x": 0}).values()) >= self.deps.settings.draft_min_judge_score,
                scores=judge.get("scores", {}),
                issues=judge_issues,
                model=self.deps.models.describe().get("judge"),
                prompt_version=PROMPT_VERSION,
            ),
        ]
        saved = await self.deps.store.create_revision(revision, evaluations)
        emit("revision_saved", revision_id=str(saved.id), revision_number=saved.revision_number, content_hash=saved.content_hash[:12])
        return {"revision_id": str(saved.id)}

    @workflow_node("await_review", None)
    async def await_review(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        if task.status == TaskStatus.VALIDATING:
            await self.deps.store.transition(task_id, TaskStatus.AWAITING_REVIEW, reason="draft_ready")
        # Epic 4 resumes this with the owner's review decision.
        review = interrupt({"type": "awaiting_review", "revision_id": state.get("revision_id")})
        return {"review": review}
