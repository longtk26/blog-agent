import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.configs import config
from src.modules.shared.domain.entities import ApprovalDecision, ApprovalEntity, ArticleMetadata, PublicationTarget

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
ReviewTarget = Literal["auto", "research", "outline", "draft", "metadata", "diagram"]


class ArticleMetadataDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    slug: str = Field(min_length=3, max_length=80, pattern=SLUG_PATTERN)
    # Length/tag style limits are reported by the validators (META_*), not rejected here.
    description: str = Field(min_length=1, max_length=400)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title", "description")
    @classmethod
    def strip(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        tags = [t.strip().lower() for t in value if t.strip()]
        for tag in tags:
            if not re.fullmatch(r"[a-z0-9]{1,30}", tag):
                raise ValueError(f"Tag '{tag}' must be lowercase letters/digits only")
        return list(dict.fromkeys(tags))

    def to_entity(self) -> ArticleMetadata:
        return ArticleMetadata(**self.model_dump())


class CreateOwnerRevisionDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision_id: uuid.UUID
    markdown: str = Field(min_length=1, max_length=config.revision_max_chars)
    metadata: ArticleMetadataDto


class ReviewScopeDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[str] = Field(default_factory=list, max_length=20)
    target: ReviewTarget = "auto"

    @field_validator("sections")
    @classmethod
    def clean_sections(cls, value: list[str]) -> list[str]:
        return [s.strip()[:200] for s in value if s.strip()]


class ReviewRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["revise", "reject"]
    revision_id: uuid.UUID | None = None
    feedback: str | None = Field(default=None, max_length=4000)
    scope: ReviewScopeDto = Field(default_factory=ReviewScopeDto)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_action(self) -> "ReviewRequestDto":
        if self.action == "revise":
            if self.revision_id is None:
                raise ValueError("revision_id is required to request a revision")
            if not (self.feedback or "").strip() or len(self.feedback.strip()) < 3:
                raise ValueError("feedback is required to request a revision")
        return self


class ApprovalOptionsDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    devto_mode: Literal["draft", "published"] = "draft"


class CreateApprovalDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destinations: list[PublicationTarget] = Field(min_length=1, max_length=len(PublicationTarget))
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    options: ApprovalOptionsDto = Field(default_factory=ApprovalOptionsDto)
    acknowledge_blockers: bool = False

    @field_validator("destinations")
    @classmethod
    def unique(cls, value: list[PublicationTarget]) -> list[PublicationTarget]:
        return list(dict.fromkeys(value))


class ApprovalDto(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    article_revision_id: uuid.UUID
    content_hash: str
    destination: PublicationTarget
    options: dict
    decision: ApprovalDecision
    reviewer_id: str
    reviewed_at: datetime
    superseded_at: datetime | None

    @classmethod
    def from_entity(cls, approval: ApprovalEntity) -> "ApprovalDto":
        return cls(**approval.model_dump())


class ApprovalListResponseDto(BaseModel):
    items: list[ApprovalDto]
