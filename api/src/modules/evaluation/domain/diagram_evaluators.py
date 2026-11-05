"""Diagram quality evaluators (E10-S8).

diagram_visual_quality  1 - (0.25 x major + 0.05 x minor), floored at 0, averaged over the task's diagrams.
                        Uses the review stored with each asset (E10-S7). When an asset has none (review disabled,
                        skipped, or a run from before Epic 10), the same reviewer prompt is run on its PNG, so a
                        baseline from older code is scored the same way.
diagram_icons_resolved  share of icon nodes whose key is in the icon catalogue (unknown keys render as plain boxes).

Both read `outputs["diagram_assets"]` (dicts as produced by run_eval's predict()).
"""

from pathlib import Path
from typing import Any

from src.modules.diagrams.domain.icons import lookup
from src.modules.diagrams.domain.schemas.diagram_review import DiagramReview, review_score
from src.modules.evaluation.domain.deterministic_evaluators import _extract_io

REVIEWED = ("passed", "issues")


def _expected(inputs: dict, reference: dict) -> bool:
    return bool(reference.get("diagram_expected") or inputs.get("include_diagram") in ("yes", True))


def eval_diagram_icons_resolved(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _, outputs, _ = _extract_io(args, kwargs)
    total = resolved = 0
    unknown: list[str] = []
    for asset in outputs.get("diagram_assets", []) or []:
        for node in (asset.get("spec") or {}).get("nodes", []):
            key = node.get("icon")
            if not key:
                continue
            total += 1
            if lookup(key):
                resolved += 1
            else:
                unknown.append(key)
    if total == 0:
        return {"key": "diagram_icons_resolved", "score": 1.0, "comment": "No icon nodes"}
    comment = f"{resolved}/{total} icon keys resolved" + (f"; unknown: {', '.join(sorted(set(unknown)))}" if unknown else "")
    return {"key": "diagram_icons_resolved", "score": round(resolved / total, 4), "comment": comment}


async def _review_png(path: str, asset: dict, model) -> DiagramReview:
    from src.modules.agent.nodes.llm import invoke_structured
    from src.modules.agent.prompts.diagram_review import review_messages

    spec = asset.get("spec") or {}
    labels = [n.get("label", "") for n in spec.get("nodes", [])] or [p.get("label", "") for p in spec.get("participants", [])]
    messages = review_messages(Path(path).read_bytes(), spec.get("title", ""), spec.get("type", ""), labels)
    return await invoke_structured(model, DiagramReview, messages, run_name="eval_diagram_visual_quality")


async def eval_diagram_visual_quality(*args: Any, model=None, **kwargs: Any) -> dict[str, Any]:
    inputs, outputs, reference = _extract_io(args, kwargs)
    assets = outputs.get("diagram_assets", []) or []
    if not assets:
        if _expected(inputs, reference):
            return {"key": "diagram_visual_quality", "score": 0.0, "comment": "Diagram expected but none was produced"}
        return {"key": "diagram_visual_quality", "score": None, "comment": "No diagram expected"}

    scores, notes = [], []
    for asset in assets:
        review = asset.get("review") or {}
        if review.get("status") in REVIEWED:
            major, minor = int(review.get("major", 0)), int(review.get("minor", 0))
            source = "stored"
        elif asset.get("png_path") and Path(asset["png_path"]).is_file():
            if model is None:
                from src.modules.agent.infrastructure.adapters.langchain_model_factory import get_model_factory
                from src.modules.agent.ports.output.model_factory import ModelRole

                model = get_model_factory().get(ModelRole.VISION)
            fresh = await _review_png(asset["png_path"], asset, model)
            major, minor = fresh.major, fresh.minor
            source = "reviewed now"
        else:
            notes.append(f"{asset.get('slot_id')}: no review and no PNG")
            continue
        scores.append(review_score(major, minor))
        notes.append(f"{asset.get('slot_id')}: {major} major / {minor} minor ({source})")
    if not scores:
        return {"key": "diagram_visual_quality", "score": None, "comment": "; ".join(notes)}
    return {"key": "diagram_visual_quality", "score": round(sum(scores) / len(scores), 4), "comment": "; ".join(notes)}
