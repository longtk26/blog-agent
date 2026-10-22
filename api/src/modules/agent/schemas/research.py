"""Structured outputs requested from the LLM during research.

Schemas carry descriptions but no length/range constraints: providers differ in which JSON-schema
keywords they accept, so limits are enforced in code after parsing (see `normalize_*`)."""

import re

from pydantic import BaseModel, Field

from src.modules.shared.domain.entities import SourceType


class PlannedQuestion(BaseModel):
    id: str = Field(description="Short stable id: Q1, Q2, ...")
    question: str = Field(description="A focused research question the article must answer")
    must_cover: bool = Field(default=False, description="True if this question comes from the owner's explicit requirements")


class PlannedQuery(BaseModel):
    query: str = Field(description="A web search query (keywords, not a sentence), under 15 words")
    intent: str = Field(description="What this query is meant to find")
    question_ids: list[str] = Field(default_factory=list, description="Ids of the questions this query serves")
    preferred_source_types: list[SourceType] = Field(
        default_factory=list, description="Source types that would best answer this query"
    )


class ResearchPlanOut(BaseModel):
    questions: list[PlannedQuestion] = Field(description="3-8 research questions, most important first")
    queries: list[PlannedQuery] = Field(description="Search queries covering every question")
    must_cover: list[str] = Field(default_factory=list, description="Explicit requirements from the owner, restated")
    out_of_scope: list[str] = Field(default_factory=list, description="Topics deliberately excluded")


class FollowUpQueriesOut(BaseModel):
    queries: list[PlannedQuery] = Field(description="New search queries that target only the unanswered questions")


class ClaimOut(BaseModel):
    text: str = Field(description="One factual statement the source supports, in your own words")
    supporting_quote: str = Field(
        description="A short exact quote (max ~300 characters) copied verbatim from the source text that supports the claim"
    )
    question_id: str | None = Field(default=None, description="Id of the research question this claim helps answer")


class SourceAssessmentOut(BaseModel):
    source_type: SourceType
    quality_score: float = Field(description="0.0-1.0: authority, accuracy, recency and primary-ness of the source")
    quality_rationale: str = Field(description="One or two sentences justifying the score")
    relevance: float = Field(description="0.0-1.0: how relevant the source is to the research questions")
    notes: list[str] = Field(default_factory=list, description="Up to 8 concise research notes")
    claims: list[ClaimOut] = Field(default_factory=list, description="Up to 8 claims with verbatim supporting quotes")


class KeyFindingOut(BaseModel):
    finding: str
    claim_refs: list[str] = Field(description="Claim refs like C3 that support this finding")


class ConflictOut(BaseModel):
    description: str
    claim_refs: list[str] = Field(default_factory=list)


class AngleOut(BaseModel):
    title: str = Field(description="Working title for an article with this angle")
    audience: str = Field(description="Who this angle serves best")
    rationale: str


class ResearchBriefOut(BaseModel):
    summary: str = Field(description="3-6 sentence summary of what the research found")
    key_findings: list[KeyFindingOut]
    conflicts: list[ConflictOut] = Field(default_factory=list, description="Places where sources disagree")
    open_questions: list[str] = Field(default_factory=list, description="Questions the research could not answer")
    angles: list[AngleOut] = Field(description="2-3 suggested article angles")
    recommended_source_refs: list[str] = Field(description="Source refs like S2, best first")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def normalize_plan(plan: ResearchPlanOut, max_queries: int, max_questions: int = 8) -> ResearchPlanOut:
    questions = [q for q in plan.questions if q.question.strip()][:max_questions]
    seen: set[str] = set()
    for index, question in enumerate(questions, start=1):
        if not re.fullmatch(r"Q\d{1,2}", question.id or "") or question.id in seen:
            question.id = f"Q{index}"
        seen.add(question.id)
    valid_ids = {q.id for q in questions}
    queries = normalize_queries(plan.queries, valid_ids, max_queries)
    return ResearchPlanOut(
        questions=questions,
        queries=queries,
        must_cover=[m for m in plan.must_cover if m.strip()][:10],
        out_of_scope=[o for o in plan.out_of_scope if o.strip()][:10],
    )


def normalize_queries(queries: list[PlannedQuery], valid_ids: set[str], limit: int, exclude: set[str] | None = None) -> list[PlannedQuery]:
    result: list[PlannedQuery] = []
    seen = {q.lower() for q in exclude or set()}
    for query in queries:
        text = " ".join(query.query.split())[:300]
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        query.query = text
        query.question_ids = [qid for qid in query.question_ids if qid in valid_ids]
        result.append(query)
        if len(result) >= limit:
            break
    return result


def normalize_assessment(assessment: SourceAssessmentOut, valid_question_ids: set[str]) -> SourceAssessmentOut:
    assessment.quality_score = _clamp(assessment.quality_score)
    assessment.relevance = _clamp(assessment.relevance)
    assessment.notes = [n.strip() for n in assessment.notes if n.strip()][:8]
    claims = []
    for claim in assessment.claims[:8]:
        if not claim.text.strip() or not claim.supporting_quote.strip():
            continue
        claim.supporting_quote = claim.supporting_quote.strip()[:400]
        if claim.question_id not in valid_question_ids:
            claim.question_id = None
        claims.append(claim)
    assessment.claims = claims
    return assessment
