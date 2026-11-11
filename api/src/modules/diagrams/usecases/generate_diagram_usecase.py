"""Generate, lay out, render, review and persist a diagram for one article slot (Epic 7, reworked in Epic 10).

    spec (LLM, structured) -> geometry + layout lint -> .drawio -> draw.io render (SVG + PNG, XML embedded)
        -> vision review of the PNG -> issues? regenerate with the issues as feedback (max N rounds) -> best candidate

The published SVG/PNG is draw.io's own export of the .drawio file (E10-S2), so readers see the real stencils and the
image re-opens as an editable diagram. The review (E10-S7) and the deterministic layout lint (E10-S5) both feed the
existing `feedback` argument of the diagram prompt; the candidate with the fewest major issues wins, not the last one.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from src.configs.config import config
from src.configs.logger import get_logger
from src.modules.agent.ports.output.model_factory import IModelFactory, ModelRole
from src.modules.agent.prompts.diagram import diagram_messages
from src.modules.agent.prompts.diagram_review import review_messages
from src.modules.diagrams.domain.diagram_builder import build_diagram
from src.modules.diagrams.domain.drawio_validator import validate_drawio_xml
from src.modules.diagrams.domain.layout_lint import LintFinding
from src.modules.diagrams.domain.readability import column_width_finding
from src.modules.diagrams.domain.mermaid_generator import choose_diagram_format, generate_mermaid
from src.modules.diagrams.domain.schemas.diagram_review import CHECKLIST, DiagramReview
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec
from src.modules.diagrams.domain.spec_validator import validate_spec
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer, RenderResult
from src.modules.diagrams.ports.output.diagram_repository import IDiagramAssetRepository
from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity
from src.modules.shared.domain.entities.writing_task_entity import WritingTaskEntity

logger = get_logger(__name__)


@dataclass
class RenderedDiagram:
    """One generation for a slot: its sources, the render readers would see, and what review found."""

    spec: DiagramSpec
    format: str                       # drawio | mermaid
    source: str                       # .drawio XML or Mermaid code
    svg: str
    png: bytes | None
    sha256: str
    lint: list[LintFinding] = field(default_factory=list)
    review: DiagramReview | None = None
    review_status: str = "disabled"   # disabled | passed | issues | skipped (no PNG / model error)
    round: int = 0

    @property
    def major(self) -> int:
        return (self.review.major if self.review else 0) + len(self.lint)

    @property
    def minor(self) -> int:
        return self.review.minor if self.review else 0

    def rank(self) -> tuple[int, int, int]:
        # Fewest major issues (vision + lint), then fewest minor, then the later round (it saw more feedback).
        return (self.major, self.minor, -self.round)

    def review_record(self, rounds: int) -> dict[str, Any]:
        return {
            "status": self.review_status,
            "passed": self.review_status in ("passed", "disabled", "skipped") and not self.lint,
            "major": self.major,
            "minor": self.minor,
            "issues": [i.model_dump() for i in self.review.issues] if self.review else [],
            "lint": [{"check": f.check, "message": f.message} for f in self.lint],
            "rounds": rounds,
            "chosen_round": self.round,
        }


def review_feedback(candidate: RenderedDiagram) -> str:
    """Issues of a rendered candidate, phrased as feedback for the next DiagramSpec generation."""
    lines = []
    if candidate.review:
        for issue in candidate.review.issues:
            where = f" ({', '.join(issue.labels_involved)})" if issue.labels_involved else ""
            lines.append(f"- [{issue.severity}] {CHECKLIST[issue.check]} {issue.description}{where}")
    for finding in candidate.lint:
        lines.append(f"- [layout] {finding.message}")
    return (
        "An automated review of the rendered diagram found these readability problems. Change the spec so they "
        "cannot happen: shorter labels, fewer or merged edges, a different direction, moving a node to the group it "
        "talks to, or splitting a busy node.\n" + "\n".join(lines)
    )


def store_render(task_dir: Path, clean_slot: str, svg: str, png: bytes | None) -> tuple[str, str | None]:
    """Write a render's SVG (+ PNG, or remove a stale one) next to the source; returns (svg_path, png_path)."""
    svg_file = task_dir / f"{clean_slot}.svg"
    svg_file.write_text(svg, encoding="utf-8")
    png_file = task_dir / f"{clean_slot}.png"
    if png:
        png_file.write_bytes(png)
        return str(svg_file), str(png_file)
    png_file.unlink(missing_ok=True)
    return str(svg_file), None


class GenerateDiagramUsecase:
    def __init__(
        self,
        models: IModelFactory,
        renderer: IDiagramRenderer,
        repository: IDiagramAssetRepository,
        settings=None,
    ):
        self.models = models
        self.renderer = renderer
        self.repository = repository
        self.settings = settings or config

    async def execute(
        self,
        task: WritingTaskEntity,
        slot_id: str,
        section_heading: str,
        section_goal: str,
        section_text: str | None = None,
        claims_text: str | None = None,
        feedback: str | None = None,
        forced_format: str | None = None,
        callbacks: list[Any] | None = None,
    ) -> tuple[DiagramAssetEntity, str]:
        """Generate the diagram for a slot and return (asset, markdown snippet)."""
        review_on = bool(self.settings.diagram_visual_review)
        extra_rounds = max(0, int(self.settings.diagram_review_max_rounds)) if review_on else 0

        candidates: list[RenderedDiagram] = []
        auto_feedback: str | None = None
        for round_no in range(extra_rounds + 1):
            spec = await self._generate_spec_with_repair(
                article_title=task.topic,
                section_heading=section_heading,
                section_goal=section_goal,
                section_text=section_text,
                claims_text=claims_text,
                feedback="\n\n".join(f for f in (feedback, auto_feedback) if f) or None,
                callbacks=callbacks,
            )
            format_choice = forced_format or choose_diagram_format(spec, task.diagram_format)
            candidate = await self._render(spec, format_choice)
            candidate.round = round_no
            if review_on:
                await self._review(candidate, slot_id, callbacks)
            candidates.append(candidate)
            if candidate.major == 0:
                break
            checks = [f.check for f in candidate.lint] + [
                f"review#{i.check}" for i in (candidate.review.issues if candidate.review else []) if i.severity == "major"
            ]
            logger.info(
                f"Diagram {slot_id} round {round_no}: {candidate.major} major / {candidate.minor} minor issues"
                f" ({', '.join(checks)})"
                + ("; regenerating with review feedback" if round_no < extra_rounds else "; keeping the best round")
            )
            auto_feedback = review_feedback(candidate)

        best = min(candidates, key=RenderedDiagram.rank)
        await self._trace_summary(best, len(candidates), slot_id, callbacks)
        return self._persist(task, slot_id, best, len(candidates))

    # --- steps ----------------------------------------------------------------------------------

    async def _render(self, spec: DiagramSpec, format_choice: str) -> RenderedDiagram:
        if format_choice == "mermaid":
            code = generate_mermaid(spec)
            try:
                out = await self.renderer.render_mermaid(code)
            except Exception as exc:
                # The site renders the ```mermaid fence itself; the SVG is only the Dev.to fallback.
                logger.warning(f"Mermaid rendering via renderer failed: {exc}")
                placeholder = f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"><text>{spec.title}</text></svg>'
                out = RenderResult(svg=placeholder, png_bytes=None, sha256=hashlib.sha256(code.encode("utf-8")).hexdigest())
            return RenderedDiagram(spec, "mermaid", code, out.svg, out.png_bytes, out.sha256)

        built = build_diagram(spec)
        check = validate_drawio_xml(built.drawio_xml, spec)
        if not check.is_valid:
            # Only reachable with a best-effort spec (repair attempts exhausted): publish what is valid, but say so.
            logger.warning(f"draw.io XML for {spec.title!r} failed validation: {'; '.join(check.errors[:5])}")
        # draw.io itself renders what readers see (E10-S2). Renderer down -> raise; the node skips this diagram.
        out = await self.renderer.render_drawio(built.drawio_xml, embed_diagram=True)
        lint = list(built.lint)
        # Epic 14: DEV shows body images at 800px; a too-wide diagram counts as a major issue and is regenerated.
        too_wide = column_width_finding(
            out.png_bytes,
            getattr(self.settings, "diagram_column_width_px", 800),
            getattr(self.settings, "diagram_min_text_px", 11.0),
        )
        if too_wide:
            lint.append(too_wide)
        return RenderedDiagram(spec, "drawio", built.drawio_xml, out.svg, out.png_bytes, out.sha256, lint=lint)

    async def _review(self, candidate: RenderedDiagram, slot_id: str, callbacks: list[Any] | None) -> None:
        if not candidate.png:
            candidate.review_status = "skipped"
            return
        labels = [n.label for n in candidate.spec.nodes] or [p.label for p in candidate.spec.participants]
        messages = review_messages(candidate.png, candidate.spec.title, candidate.spec.type, labels)
        run_cfg: dict[str, Any] = {
            "run_name": "review_diagram",
            "tags": ["node:review_diagram"],
            "metadata": {"node": "review_diagram", "slot_id": slot_id, "round": candidate.round, "format": candidate.format},
        }
        if callbacks:
            run_cfg["callbacks"] = callbacks
        try:
            model = self.models.get(ModelRole.VISION).with_structured_output(DiagramReview)
            result = await model.ainvoke(messages, config=run_cfg)
            review = result if isinstance(result, DiagramReview) else DiagramReview.model_validate(result)
        except Exception as exc:
            # The diagram is kept; only the review is missing (E10-S7).
            logger.warning(f"Diagram review failed for {slot_id}: {type(exc).__name__}: {str(exc)[:300]}")
            candidate.review_status = "skipped"
            return
        candidate.review = review
        candidate.review_status = "passed" if review.major == 0 else "issues"

    async def _trace_summary(self, best: RenderedDiagram, rounds: int, slot_id: str, callbacks: list[Any] | None) -> None:
        """A tiny traced run whose metadata makes diagram quality filterable in LangSmith (E10-S7)."""
        if not callbacks:
            return
        metadata = {
            "slot_id": slot_id,
            "diagram_format": best.format,
            "diagram_review_status": best.review_status,
            "diagram_review_passed": best.major == 0,
            "diagram_review_major_issues": best.major,
            "diagram_review_minor_issues": best.minor,
            "diagram_review_rounds": rounds,
            "diagram_lint_findings": len(best.lint),
        }
        try:
            await RunnableLambda(lambda x: x).ainvoke(
                metadata, config={"run_name": "diagram_review_summary", "metadata": metadata, "callbacks": callbacks}
            )
        except Exception as exc:  # tracing must never break generation
            logger.debug(f"diagram_review_summary trace failed: {exc}")

    def _persist(self, task: WritingTaskEntity, slot_id: str, best: RenderedDiagram, rounds: int):
        task_dir = Path(self.settings.data_dir) / "assets" / str(task.id)
        task_dir.mkdir(parents=True, exist_ok=True)
        clean_slot = slot_id.replace("/", "_")
        asset_id = uuid.uuid4()

        source_file = task_dir / f"{clean_slot}.{'mmd' if best.format == 'mermaid' else 'drawio'}"
        source_file.write_text(best.source, encoding="utf-8")
        svg_path, png_path = store_render(task_dir, clean_slot, best.svg, best.png)

        if best.format == "mermaid":
            snippet = f"\n```mermaid\n{best.source}\n```\n"
        else:
            snippet = f'\n![{best.spec.title}](asset://{asset_id} "{best.spec.title}")\n'

        asset = DiagramAssetEntity(
            id=asset_id,
            task_id=task.id,
            slot_id=slot_id,
            format=best.format,
            spec=best.spec.model_dump(),
            source_path=str(source_file),
            svg_path=svg_path,
            png_path=png_path,
            sha256=best.sha256,
            validation_status="valid" if best.major == 0 else "warning",
            review=best.review_record(rounds),
            review_rounds=rounds,
        )
        return self.repository.create(asset), snippet

    async def _generate_spec_with_repair(
        self,
        article_title: str,
        section_heading: str,
        section_goal: str,
        section_text: str | None,
        claims_text: str | None,
        feedback: str | None,
        callbacks: list[Any] | None = None,
    ) -> DiagramSpec:
        model = self.models.get(ModelRole.PLANNER).with_structured_output(DiagramSpec)
        messages = diagram_messages(
            article_title=article_title,
            section_heading=section_heading,
            section_goal=section_goal,
            section_text=section_text,
            claims_text=claims_text,
            feedback=feedback,
        )
        run_cfg: dict[str, Any] = {"run_name": "generate_diagram_spec", "metadata": {"node": "generate_diagram_spec"}}
        if callbacks:
            run_cfg["callbacks"] = callbacks

        spec = await model.ainvoke(messages, config=run_cfg)
        errors = validate_spec(spec)
        if not errors:
            return spec

        # Repair loop up to 2 retries (E7-S1)
        for attempt in range(2):
            logger.info(f"DiagramSpec validation attempt {attempt + 1} failed: {errors}. Retrying...")
            repair_messages = list(messages) + [
                AIMessage(content=spec.model_dump_json()),
                HumanMessage(
                    content=(
                        "Your DiagramSpec contained the following validation errors. Please fix them:\n"
                        + "\n".join(f"- {e}" for e in errors)
                    )
                ),
            ]
            spec = await model.ainvoke(repair_messages, config=run_cfg)
            errors = validate_spec(spec)
            if not errors:
                return spec

        logger.warning(f"DiagramSpec still had validation errors after 2 retries: {errors}. Proceeding with best-effort.")
        return spec
