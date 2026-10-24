import uuid
from datetime import datetime

from pydantic import BaseModel

from src.modules.shared.domain.entities import (
    ApprovalEntity,
    ArticleRevisionEntity,
    EvaluationResultEntity,
    RevisionAuthor,
    ValidationIssue,
)


class EvaluationDto(BaseModel):
    kind: str
    passed: bool
    scores: dict
    issues: list[ValidationIssue]
    model: str | None
    prompt_version: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, evaluation: EvaluationResultEntity) -> "EvaluationDto":
        return cls(**evaluation.model_dump(exclude={"id", "revision_id"}))


class RevisionSummaryDto(BaseModel):
    id: uuid.UUID
    revision_number: int
    parent_revision_id: uuid.UUID | None
    created_by: RevisionAuthor
    title: str
    slug: str
    content_hash: str
    word_count: int | None
    checks_passed: dict[str, bool]
    feedback: str | None            # owner feedback that produced this AI revision
    review_target: str | None
    sections_changed: list[str]
    out_of_scope: list[str]         # changed sections the owner did not ask about
    approved_for: list[str]         # destinations with a live (not superseded) approval
    created_at: datetime

    @classmethod
    def from_entity(
        cls, revision: ArticleRevisionEntity, evaluations: list[EvaluationResultEntity], approvals: list[ApprovalEntity] | None = None
    ) -> "RevisionSummaryDto":
        review = revision.metadata.get("review") or {}
        return cls(
            **revision.model_dump(
                include={"id", "revision_number", "parent_revision_id", "created_by", "title", "slug", "content_hash", "created_at"}
            ),
            word_count=revision.metadata.get("word_count"),
            checks_passed={e.kind: e.passed for e in evaluations},
            feedback=review.get("feedback"),
            review_target=review.get("target"),
            sections_changed=revision.metadata.get("sections_changed", []),
            out_of_scope=review.get("out_of_scope", []),
            approved_for=sorted(
                str(a.destination) for a in approvals or [] if a.article_revision_id == revision.id and a.decision == "approved"
            ),
        )


class RevisionListResponseDto(BaseModel):
    items: list[RevisionSummaryDto]


class RevisionResponseDto(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    revision_number: int
    parent_revision_id: uuid.UUID | None
    created_by: RevisionAuthor
    title: str
    slug: str
    description: str
    tags: list[str]
    markdown: str
    content_hash: str
    metadata: dict
    evaluations: list[EvaluationDto]
    created_at: datetime

    @classmethod
    def from_entity(cls, revision: ArticleRevisionEntity, evaluations: list[EvaluationResultEntity]) -> "RevisionResponseDto":
        return cls(**revision.model_dump(), evaluations=[EvaluationDto.from_entity(e) for e in evaluations])
