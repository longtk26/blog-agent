import asyncio
import hashlib
import uuid
from datetime import datetime, timezone

from langgraph.types import interrupt

from src.configs.logger import Redactor, get_logger
from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.graph.state import BlogState
from src.modules.agent.nodes.base import emit, safe_error, workflow_node
from src.modules.agent.nodes.brief_render import render_brief_markdown
from src.modules.agent.nodes.evidence import quote_in_text
from src.modules.agent.nodes.llm import invoke_structured
from src.modules.agent.ports.output.model_factory import ModelRole
from src.modules.agent.prompts.research import (
    assess_source_messages,
    follow_up_messages,
    plan_research_messages,
    synthesize_messages,
)
from src.modules.agent.schemas import (
    FollowUpQueriesOut,
    ResearchBriefOut,
    ResearchPlanOut,
    SourceAssessmentOut,
    normalize_assessment,
    normalize_plan,
    normalize_queries,
)
from src.modules.agent.tools import make_search_tool
from src.modules.research.infrastructure.adapters.url_tools import (
    canonicalize_url,
    domain_matches,
    host_of,
    is_http_url,
)
from src.modules.research.ports.output import ExtractionError, SearchError, SearchResult
from src.modules.shared.domain.entities import (
    ResearchBriefEntity,
    ResearchClaimEntity,
    ResearchSourceEntity,
    SourceStatus,
    TaskProgress,
)
from src.modules.shared.domain.value_objects import TaskStatus

logger = get_logger(__name__)

MAX_STORED_CHARS = 200_000
MIN_TEXT_CHARS = 200
MAX_EVIDENCE_CLAIMS = 60
USABLE = (SourceStatus.ASSESSED, SourceStatus.LOW_QUALITY)


def _task_id(state: BlogState) -> uuid.UUID:
    return uuid.UUID(state["task_id"])


def _source_refs(sources: list[ResearchSourceEntity]) -> dict[uuid.UUID, str]:
    """Stable short refs (S1, S2, ...) in creation order, used in prompts instead of UUIDs."""
    return {source.id: f"S{index}" for index, source in enumerate(sources, start=1)}


class ResearchNodes:
    def __init__(self, deps: WorkflowDeps):
        self.deps = deps
        self.search_tool = make_search_tool(deps.search)
        self.redactor = Redactor(deps.settings.secret_values())

    async def _budgets(self, task):
        settings = self.deps.settings
        budgets = task.budgets
        budgets.max_queries = min(budgets.max_queries, settings.research_max_queries)
        budgets.max_sources = min(budgets.max_sources, settings.research_max_sources)
        budgets.max_research_rounds = min(budgets.max_research_rounds, settings.research_max_rounds)
        return budgets

    async def _progress(self, state: BlogState, **overrides) -> None:
        task_id = _task_id(state)
        counts = await self.deps.store.source_counts(task_id)
        claims = await self.deps.store.list_claims(task_id)
        progress = TaskProgress(
            round=overrides.get("round", state.get("round", 0)),
            queries_used=overrides.get("queries_used", len(state.get("done_queries", []))),
            sources_found=sum(counts.values()),
            sources_extracted=sum(counts.get(s, 0) for s in ("extracted", "assessed", "low_quality")),
            sources_assessed=sum(counts.get(s, 0) for s in ("assessed", "low_quality")),
            claims=len(claims),
        )
        await self.deps.store.update_task(task_id, progress=progress)
        emit("budget_update", **progress.model_dump())

    # --- plan -------------------------------------------------------------------------------

    @workflow_node("plan_research", TaskStatus.RESEARCHING, timeout_seconds=300)
    async def plan_research(self, state: BlogState) -> dict:
        task = await self.deps.store.get_task(_task_id(state))
        budgets = await self._budgets(task)
        model = self.deps.models.get(ModelRole.PLANNER)
        plan = await invoke_structured(model, ResearchPlanOut, plan_research_messages(task, budgets.max_queries))
        plan = normalize_plan(plan, budgets.max_queries)
        if not plan.questions or not plan.queries:
            raise ValueError("Research plan has no questions or queries")

        plan_dict = plan.model_dump(mode="json")
        await self.deps.store.update_task(task.id, research_plan=plan_dict)
        emit("plan_ready", questions=len(plan.questions), queries=len(plan.queries))
        update = {"plan": plan_dict, "round": 1, "pending_queries": plan_dict["queries"], "done_queries": [], "mode": str(task.mode)}
        await self._progress({**state, **update})
        return update

    # --- search -----------------------------------------------------------------------------

    @workflow_node("search", TaskStatus.RESEARCHING, timeout_seconds=300)
    async def search(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        budgets = await self._budgets(task)
        done = list(state.get("done_queries", []))
        queries = state.get("pending_queries", [])[: max(0, budgets.max_queries - len(done))]

        known = await self.deps.store.known_urls(task_id)
        remaining_sources = max(0, budgets.max_sources - len(known))
        denylist = self.deps.settings.research_domain_denylist

        ran: list[tuple[dict, list[SearchResult]]] = []
        failures = 0
        for query in queries:
            if remaining_sources <= 0:
                break
            try:
                raw = await self.search_tool.ainvoke(
                    {"query": query["query"], "max_results": budgets.results_per_query, "exclude_domains": denylist or None}
                )
                results = [SearchResult.model_validate(item) for item in raw]
            except SearchError as exc:
                failures += 1
                emit("search_failed", query=query["query"], message=safe_error(exc, self.redactor))
                results = []
            done.append(query["query"])
            ran.append((query, results))
            emit("query_issued", query=query["query"], results=len(results))

        if queries and failures == len(ran) and not known:
            raise SearchError("All searches failed; check the search provider configuration")

        # Interleave by rank so every query contributes its best results before second-best ones.
        seen = set(known)
        candidates: list[ResearchSourceEntity] = []
        for rank in range(max((len(r) for _, r in ran), default=0)):
            for query, results in ran:
                if rank >= len(results):
                    continue
                result = results[rank]
                if not is_http_url(result.url):
                    continue
                canonical = canonicalize_url(result.url)
                if canonical in seen or domain_matches(host_of(result.url), denylist):
                    continue
                seen.add(canonical)
                candidates.append(
                    ResearchSourceEntity(
                        task_id=task_id,
                        url=result.url,
                        canonical_url=canonical,
                        title=result.title,
                        snippet=(result.snippet or "")[:1000] or None,
                        published_at=result.published_date,
                        query=query["query"],
                        round=state.get("round", 1),
                    )
                )

        inserted = await self.deps.store.add_sources(candidates[:remaining_sources])
        for source in inserted:
            emit("source_found", source_id=str(source.id), title=source.title, url=source.url)
        update = {"pending_queries": [], "done_queries": done}
        await self._progress({**state, **update})
        return update

    # --- extract ----------------------------------------------------------------------------

    @workflow_node("extract_pages", TaskStatus.RESEARCHING, timeout_seconds=600)
    async def extract_pages(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        pending = await self.deps.store.list_sources(task_id, [SourceStatus.PENDING])
        limit = asyncio.Semaphore(self.deps.settings.extract_concurrency)

        async def extract_one(source: ResearchSourceEntity) -> None:
            async with limit:
                try:
                    page = await self.deps.extractor.extract(source.url)
                    text = page.text.strip()
                    if len(text) < MIN_TEXT_CHARS:
                        raise ExtractionError(f"Too little readable text ({len(text)} chars)")
                except Exception as exc:
                    source.status = SourceStatus.FAILED
                    source.error = safe_error(exc, self.redactor) if not isinstance(exc, ExtractionError) else str(exc)[:500]
                    await self.deps.store.update_source(source)
                    emit("source_failed", source_id=str(source.id), url=source.url, message=source.error)
                    return

                source.content_text = text[:MAX_STORED_CHARS]
                source.content_hash = hashlib.sha256(text.encode()).hexdigest()
                source.title = page.title or source.title
                source.publisher = page.publisher or host_of(page.final_url or source.url).removeprefix("www.")
                source.published_at = source.published_at or page.published_at
                source.retrieved_at = datetime.now(timezone.utc)
                source.status = SourceStatus.EXTRACTED
                source.error = None
                await self.deps.store.update_source(source)
                emit("source_extracted", source_id=str(source.id), title=source.title, chars=len(text))

        await asyncio.gather(*(extract_one(source) for source in pending))
        await self._progress(state)
        return {}

    # --- assess -----------------------------------------------------------------------------

    @workflow_node("assess_sources", TaskStatus.RESEARCHING, timeout_seconds=900)
    async def assess_sources(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        questions = state["plan"]["questions"]
        question_ids = {q["id"] for q in questions}
        refs = _source_refs(await self.deps.store.list_sources(task_id))
        to_assess = await self.deps.store.list_sources(task_id, [SourceStatus.EXTRACTED], include_content=True)
        model = self.deps.models.get(ModelRole.FAST)
        settings = self.deps.settings
        limit = asyncio.Semaphore(settings.assess_concurrency)
        failures = 0

        async def assess_one(source: ResearchSourceEntity) -> None:
            nonlocal failures
            async with limit:
                messages = assess_source_messages(
                    task,
                    questions,
                    refs.get(source.id, "S?"),
                    source.url,
                    source.title,
                    source.publisher,
                    (source.content_text or "")[: settings.research_source_chars_for_llm],
                )
                try:
                    assessment = await invoke_structured(model, SourceAssessmentOut, messages)
                except Exception as exc:
                    failures += 1
                    source.status = SourceStatus.FAILED
                    source.error = f"Assessment failed: {safe_error(exc, self.redactor)}"
                    await self.deps.store.update_source(source)
                    emit("source_failed", source_id=str(source.id), url=source.url, message=source.error)
                    return

            assessment = normalize_assessment(assessment, question_ids)
            claims = [
                ResearchClaimEntity(
                    task_id=task_id,
                    source_id=source.id,
                    question_id=claim.question_id,
                    text=claim.text.strip(),
                    supporting_quote=claim.supporting_quote,
                    quote_verified=quote_in_text(claim.supporting_quote, source.content_text),
                )
                for claim in assessment.claims
            ]
            low_quality = assessment.quality_score < settings.research_quality_threshold
            source.source_type = assessment.source_type
            source.quality_score = assessment.quality_score
            source.quality_rationale = assessment.quality_rationale
            source.relevance = assessment.relevance
            source.notes = assessment.notes
            source.status = SourceStatus.LOW_QUALITY if low_quality else SourceStatus.ASSESSED
            await self.deps.store.save_assessment(source, claims)
            emit(
                "source_assessed",
                source_id=str(source.id),
                title=source.title,
                quality=assessment.quality_score,
                claims=len(claims),
                verified_claims=sum(c.quote_verified for c in claims),
                low_quality=low_quality,
            )

        await asyncio.gather(*(assess_one(source) for source in to_assess))
        if to_assess and failures == len(to_assess):
            raise RuntimeError("Every source assessment failed; check the LLM configuration")
        await self._progress(state)
        return {}

    # --- coverage loop ----------------------------------------------------------------------

    @workflow_node("check_coverage", TaskStatus.RESEARCHING, timeout_seconds=300)
    async def check_coverage(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        budgets = await self._budgets(task)
        questions = state["plan"]["questions"]
        sources = {s.id: s for s in await self.deps.store.list_sources(task_id)}
        claims = await self.deps.store.list_claims(task_id)
        threshold = self.deps.settings.research_quality_threshold

        supported = {
            claim.question_id
            for claim in claims
            if claim.question_id
            and (source := sources.get(claim.source_id)) is not None
            and source.status == SourceStatus.ASSESSED
            and (source.quality_score or 0) >= threshold
        }
        gaps = [q["id"] for q in questions if q["id"] not in supported]
        round_number = state.get("round", 1)
        done = state.get("done_queries", [])
        emit("coverage_checked", round=round_number, supported=sorted(supported), gaps=gaps)

        can_continue = (
            gaps
            and round_number < budgets.max_research_rounds
            and len(done) < budgets.max_queries
            and len(sources) < budgets.max_sources
        )
        if can_continue:
            remaining = budgets.max_queries - len(done)
            gap_questions = [q for q in questions if q["id"] in gaps]
            follow_up = await invoke_structured(
                self.deps.models.get(ModelRole.PLANNER),
                FollowUpQueriesOut,
                follow_up_messages(task, gap_questions, done, remaining),
            )
            queries = normalize_queries(follow_up.queries, set(gaps), remaining, exclude=set(done))
            if queries:
                emit("follow_up_planned", round=round_number + 1, queries=[q.query for q in queries])
                return {"gaps": gaps, "round": round_number + 1, "pending_queries": [q.model_dump(mode="json") for q in queries]}

        open_questions = [q["question"] for q in questions if q["id"] in gaps]
        await self.deps.store.update_task(task_id, open_questions=open_questions)
        return {"gaps": gaps, "pending_queries": []}

    @staticmethod
    def route_after_coverage(state: BlogState) -> str:
        return "search" if state.get("pending_queries") else "synthesize_research"

    # --- synthesis --------------------------------------------------------------------------

    @workflow_node("synthesize_research", TaskStatus.RESEARCHING, timeout_seconds=600)
    async def synthesize_research(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        questions = state["plan"]["questions"]
        all_sources = await self.deps.store.list_sources(task_id)
        refs = _source_refs(all_sources)
        usable = {s.id: s for s in all_sources if s.status in USABLE}
        claims = sorted(
            (c for c in await self.deps.store.list_claims(task_id) if c.source_id in usable),
            key=lambda c: (-(usable[c.source_id].quality_score or 0), not c.quote_verified),
        )[:MAX_EVIDENCE_CLAIMS]
        claim_refs = {f"C{index}": claim for index, claim in enumerate(claims, start=1)}
        gap_texts = [q["question"] for q in questions if q["id"] in set(state.get("gaps", []))]

        if claim_refs:
            evidence = self._evidence_text(questions, claim_refs, usable, refs)
            brief = await invoke_structured(
                self.deps.models.get(ModelRole.PLANNER),
                ResearchBriefOut,
                synthesize_messages(task, questions, evidence, gap_texts),
            )
        else:
            brief = ResearchBriefOut(
                summary="The research did not find usable evidence for this topic.",
                key_findings=[],
                open_questions=[q["question"] for q in questions],
                angles=[],
                recommended_source_refs=[],
            )

        data = self._brief_data(brief, questions, claim_refs, usable, refs, gap_texts)
        saved = await self.deps.store.save_brief(
            ResearchBriefEntity(task_id=task_id, markdown=render_brief_markdown(task, data), data=data)
        )
        await self.deps.store.update_task(task_id, open_questions=data["open_questions"])
        emit("brief_ready", brief_id=str(saved.id), findings=len(data["key_findings"]))
        return {"brief_id": str(saved.id)}

    @staticmethod
    def _evidence_text(questions, claim_refs, usable, refs) -> str:
        by_question: dict[str | None, list[str]] = {}
        for ref, claim in claim_refs.items():
            source = usable[claim.source_id]
            quality = f"{source.quality_score:.2f}" if source.quality_score is not None else "?"
            flag = "" if claim.quote_verified else " [unverified quote]"
            line = f'- {ref} [{refs[source.id]} · {source.source_type or "other"} · quality {quality}] {claim.text} — "{claim.supporting_quote}"{flag}'
            by_question.setdefault(claim.question_id, []).append(line)
        sections = []
        for question in questions:
            if question["id"] in by_question:
                sections.append(f"## {question['id']}: {question['question']}\n" + "\n".join(by_question[question["id"]]))
        if None in by_question:
            sections.append("## Other evidence\n" + "\n".join(by_question[None]))
        return "\n\n".join(sections)

    @staticmethod
    def _brief_data(brief: ResearchBriefOut, questions, claim_refs, usable, refs, gap_texts) -> dict:
        ref_to_source = {ref: source for source_id, ref in refs.items() if (source := usable.get(source_id))}

        def resolve(claim_ref_list: list[str]) -> tuple[list[str], list[str]]:
            claim_ids, source_refs = [], []
            for ref in claim_ref_list:
                claim = claim_refs.get(ref.strip())
                if claim is None:
                    continue
                claim_ids.append(str(claim.id))
                source_ref = refs[claim.source_id]
                if source_ref not in source_refs:
                    source_refs.append(source_ref)
            return claim_ids, source_refs

        findings = []
        for finding in brief.key_findings:
            claim_ids, source_refs = resolve(finding.claim_refs)
            findings.append({"finding": finding.finding, "claim_ids": claim_ids, "source_refs": source_refs, "supported": bool(claim_ids)})
        conflicts = []
        for conflict in brief.conflicts:
            claim_ids, source_refs = resolve(conflict.claim_refs)
            conflicts.append({"description": conflict.description, "claim_ids": claim_ids, "source_refs": source_refs})

        recommended_refs = [r.strip() for r in brief.recommended_source_refs if r.strip() in ref_to_source]
        recommended_refs += [r for r in sorted(ref_to_source, key=lambda r: -(ref_to_source[r].quality_score or 0)) if r not in recommended_refs]
        open_questions = list(dict.fromkeys([*brief.open_questions, *gap_texts]))

        return {
            "summary": brief.summary,
            "key_findings": findings,
            "conflicts": conflicts,
            "open_questions": open_questions,
            "angles": [a.model_dump() for a in brief.angles[:3]],
            "recommended_sources": [
                {
                    "ref": ref,
                    "source_id": str(ref_to_source[ref].id),
                    "title": ref_to_source[ref].title,
                    "url": ref_to_source[ref].canonical_url,
                    "publisher": ref_to_source[ref].publisher,
                    "source_type": ref_to_source[ref].source_type,
                    "quality_score": ref_to_source[ref].quality_score,
                }
                for ref in recommended_refs[:10]
            ],
            "sources": [
                {"ref": ref, "source_id": str(s.id), "title": s.title, "url": s.canonical_url} for ref, s in ref_to_source.items()
            ],
            "questions": questions,
        }

    @staticmethod
    def route_after_synthesis(state: BlogState) -> str:
        return "await_promotion" if state.get("mode") == "research_only" else "outline"

    # --- research-only pause / article hand-off -----------------------------------------------

    @workflow_node("await_promotion", None)
    async def await_promotion(self, state: BlogState) -> dict:
        task_id = _task_id(state)
        task = await self.deps.store.get_task(task_id)
        if task.status == TaskStatus.RESEARCHING:
            await self.deps.store.transition(task_id, TaskStatus.COMPLETED, reason="research_complete")
        # Pauses the thread; `POST /tasks/{id}/promote` resumes it with the owner's choices.
        promotion = interrupt({"type": "awaiting_promotion", "task_id": state["task_id"]})
        return {"mode": "article", "promotion": promotion}
