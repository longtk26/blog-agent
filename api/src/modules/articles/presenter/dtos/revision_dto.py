import uuid
from datetime import datetime

from pydantic import BaseModel

from src.modules.shared.domain.entities import (
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
    created_by: RevisionAuthor
    title: str
    slug: str
    content_hash: str
    word_count: int | None
    checks_passed: dict[str, bool]
    created_at: datetime

    @classmethod
    def from_entity(cls, revision: ArticleRevisionEntity, evaluations: list[EvaluationResultEntity]) -> "RevisionSummaryDto":
        return cls(
            **revision.model_dump(include={"id", "revision_number", "created_by", "title", "slug", "content_hash", "created_at"}),
            word_count=revision.metadata.get("word_count"),
            checks_passed={e.kind: e.passed for e in evaluations},
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
