import json
from typing import Any, Literal
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage
from src.modules.agent.infrastructure.adapters import get_model_factory
from src.modules.agent.nodes.llm import invoke_structured
from src.modules.agent.ports.output import ModelRole
from src.modules.agent.prompts.context_files import seed_style_guide


class JudgeEvaluationOut(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Detailed justification for the score")


class PairwiseEvaluationOut(BaseModel):
    preference: Literal["A", "B", "tie"] = Field(..., description="Preferred candidate: 'A', 'B', or 'tie'")
    score: float = Field(..., description="1.0 if A preferred, 0.0 if B preferred, 0.5 if tie")
    reasoning: str = Field(..., description="Comparative justification for the preference")


def _extract_io(args: tuple, kwargs: dict) -> tuple[dict, dict, dict]:
    if len(args) >= 2 and hasattr(args[0], "outputs") and hasattr(args[1], "outputs"):
        run, example = args[0], args[1]
        inputs = getattr(run, "inputs", None) or getattr(example, "inputs", {}) or {}
        outputs = getattr(run, "outputs", {}) or {}
        reference = getattr(example, "outputs", {}) or {}
        return inputs, outputs, reference

    inputs = kwargs.get("inputs") or (args[0] if len(args) > 0 and isinstance(args[0], dict) else {})
    outputs = kwargs.get("outputs") or (args[1] if len(args) > 1 and isinstance(args[1], dict) else {})
    reference = kwargs.get("reference") or kwargs.get("reference_outputs") or (args[2] if len(args) > 2 and isinstance(args[2], dict) else {})
    return inputs, outputs, reference


async def eval_factual_support(*args: Any, model=None, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: factual_support (checked against known_facts and claim quotes)."""
    inputs, outputs, reference = _extract_io(args, kwargs)
    markdown = outputs.get("markdown", "")
    known_facts = reference.get("known_facts", [])
    claims = outputs.get("claims", [])
    quotes = [c.get("supporting_quote") for c in claims if c.get("supporting_quote")][:15]

    if not known_facts and not quotes:
        return {"key": "factual_support", "score": 1.0, "comment": "No specific facts or quotes to verify"}

    prompt = f"""You are an independent technical fact-checking evaluator.
Evaluate whether the draft article contains accurate statements consistent with the known verifiable facts and supporting source quotes.

Known Verifiable Facts:
{json.dumps(known_facts, indent=2)}

Supporting Source Quotes:
{json.dumps(quotes, indent=2)}

Draft Article (excerpt):
{markdown[:8000]}

Rate factual accuracy on a 0.0 to 1.0 scale:
- 1.0: All claims and statements align with known facts and quotes; no contradictions or hallucinated fabrications.
- 0.5: Minor inaccuracies or unsupported generalizations that do not fundamentally mislead.
- 0.0: Significant factual errors, false mathematical or code statements, or severe hallucinations.
"""
    if model is None:
        model = get_model_factory().get(ModelRole.JUDGE)

    messages = [
        SystemMessage("You evaluate factual truthfulness strictly and impartially."),
        HumanMessage(prompt),
    ]
    res = await invoke_structured(model, JudgeEvaluationOut, messages, run_name="eval_factual_support")
    return {"key": "factual_support", "score": round(res.score, 4), "comment": res.reasoning}


async def eval_must_cover_coverage(*args: Any, model=None, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: must_cover_coverage (checked against reference must_cover list)."""
    inputs, outputs, reference = _extract_io(args, kwargs)
    markdown = outputs.get("markdown", "")
    must_cover = reference.get("must_cover", [])
    if not must_cover:
        return {"key": "must_cover_coverage", "score": 1.0, "comment": "No must_cover items specified"}

    prompt = f"""You are an independent technical evaluation judge.
Evaluate how thoroughly the draft article covers each of the required topics.

Required Must-Cover Items:
{json.dumps(must_cover, indent=2)}

Draft Article (excerpt):
{markdown[:8000]}

Score must-cover coverage from 0.0 to 1.0:
- 1.0: Every required item is clearly explained with depth and appropriate technical context.
- 0.5: Some required items are mentioned briefly or superficially, but several are omitted.
- 0.0: The draft completely misses the core required items.
"""
    if model is None:
        model = get_model_factory().get(ModelRole.JUDGE)

    messages = [
        SystemMessage("You evaluate coverage of technical requirements impartially."),
        HumanMessage(prompt),
    ]
    res = await invoke_structured(model, JudgeEvaluationOut, messages, run_name="eval_must_cover_coverage")
    return {"key": "must_cover_coverage", "score": round(res.score, 4), "comment": res.reasoning}


async def eval_style_consistency(*args: Any, model=None, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: style_consistency (checked against active style guide and owner voice)."""
    inputs, outputs, reference = _extract_io(args, kwargs)
    markdown = outputs.get("markdown", "")
    _, style_guide = seed_style_guide()

    prompt = f"""You are an expert technical editor evaluating whether a blog post matches the author's writing style.

Author Style Guide:
{style_guide[:3000]}

Draft Article (excerpt):
{markdown[:8000]}

Evaluate style consistency on a 0.0 to 1.0 scale:
- 1.0: Instructive peer voice ('we', concrete numbers, named tools), no marketing hype, no filler clichés ('in today's fast-paced world'), clean headings, clear technical code/math.
- 0.5: Generally technical but contains some unnecessary filler, generic conclusions, or inconsistent voice.
- 0.0: Heavy corporate fluff, buzzword bingo, emojis, patronizing or overly simplistic tone.
"""
    if model is None:
        model = get_model_factory().get(ModelRole.JUDGE)

    messages = [
        SystemMessage("You evaluate technical writing tone, voice, and style discipline."),
        HumanMessage(prompt),
    ]
    res = await invoke_structured(model, JudgeEvaluationOut, messages, run_name="eval_style_consistency")
    return {"key": "style_consistency", "score": round(res.score, 4), "comment": res.reasoning}


async def eval_audience_depth_fit(*args: Any, model=None, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: audience_depth_fit (appropriate technical depth for target audience)."""
    inputs, outputs, reference = _extract_io(args, kwargs)
    markdown = outputs.get("markdown", "")
    audience = inputs.get("audience", "software engineers")
    depth = inputs.get("depth", "intermediate")

    prompt = f"""You are an independent technical evaluation judge.
Evaluate whether the draft article matches the intended audience and target technical depth.

Target Audience: {audience}
Target Depth: {depth}

Draft Article (excerpt):
{markdown[:8000]}

Score audience and depth fit from 0.0 to 1.0:
- 1.0: Perfectly calibrated for the specified audience and depth. Introduces neither trivial basics to seniors nor unexplained advanced concepts to beginners.
- 0.5: Mostly acceptable but slightly too shallow or overly convoluted for the stated audience.
- 0.0: Mismatched: completely misses the target audience's skill level.
"""
    if model is None:
        model = get_model_factory().get(ModelRole.JUDGE)

    messages = [
        SystemMessage("You evaluate audience targeting and pedagogical calibration."),
        HumanMessage(prompt),
    ]
    res = await invoke_structured(model, JudgeEvaluationOut, messages, run_name="eval_audience_depth_fit")
    return {"key": "audience_depth_fit", "score": round(res.score, 4), "comment": res.reasoning}


async def eval_pairwise_preference(
    inputs: dict,
    candidate_a: dict,
    candidate_b: dict,
    reference: dict | None = None,
    model=None,
) -> dict[str, Any]:
    """E9-S4: Pairwise evaluator comparing two candidate drafts for the same input.
    Returns preference ('A', 'B', 'tie'), score (1.0 for A, 0.0 for B, 0.5 for tie), and reasoning.
    """
    _, style_guide = seed_style_guide()
    topic = inputs.get("topic", "")
    requirements = inputs.get("requirements", "")
    draft_a = candidate_a.get("markdown", "")[:6000]
    draft_b = candidate_b.get("markdown", "")[:6000]

    prompt = f"""You are a head editor judging two candidate technical blog drafts written for the same request.

Topic: {topic}
Requirements: {requirements}

Author Style Guide:
{style_guide[:2000]}

Candidate A:
{draft_a}

Candidate B:
{draft_b}

Which draft better matches the author's style guide (instructive, concrete numbers, no filler clichés) and satisfies the topic requirements?
Output preference: 'A', 'B', or 'tie', with score (1.0 for A, 0.0 for B, 0.5 for tie) and concise reasoning.
"""
    if model is None:
        model = get_model_factory().get(ModelRole.JUDGE)

    messages = [
        SystemMessage("You are an impartial comparative judge choosing the superior technical draft."),
        HumanMessage(prompt),
    ]
    res = await invoke_structured(model, PairwiseEvaluationOut, messages, run_name="eval_pairwise_preference")
    return {
        "key": "pairwise_preference",
        "preference": res.preference,
        "score": res.score,
        "comment": res.reasoning,
    }


ALL_LLM_JUDGE_EVALUATORS = [
    eval_factual_support,
    eval_must_cover_coverage,
    eval_style_consistency,
    eval_audience_depth_fit,
]
