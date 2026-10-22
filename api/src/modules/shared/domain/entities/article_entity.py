import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class IssueSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class RevisionAuthor(StrEnum):
    AI = "ai"
    OWNER = "owner"


class ValidationIssue(BaseModel):
    rule: str
    severity: IssueSeverity
    message: str
    line: int | None = None
    section: str | None = None   # heading text of the section the issue is in
    source: str = "validator"    # validator | judge


class ArticleMetadata(BaseModel):
    title: str
    slug: str
    description: str
    tags: list[str] = Field(default_factory=list)


class DraftSection(BaseModel):
    """One H2 section of the working draft (the intro is section 0 with heading=None)."""

    key: str                     # stable id: "intro", "s1", "s2", ...
    heading: str | None
    heading_style: str = "numbered"   # numbered | step | plain
    goal: str = ""
    markdown: str = ""           # body without the H2 line
    claim_map: list[dict] = Field(default_factory=list)
    revisions: int = 0


class ArticleDraftEntity(BaseModel):
    """Mutable working copy while the AI drafts and self-revises; becomes an immutable revision when saved."""

    task_id: uuid.UUID
    sections: list[DraftSection] = Field(default_factory=list)
    metadata: ArticleMetadata | None = None
    markdown: str = ""
    issues: list[ValidationIssue] = Field(default_factory=list)
    judge: dict | None = None
    self_revisions: int = 0
    history: list[dict] = Field(default_factory=list)
    updated_at: datetime | None = None


class ArticleRevisionEntity(BaseModel):
    id: uuid.UUID | None = None
    task_id: uuid.UUID
    revision_number: int
    parent_revision_id: uuid.UUID | None = None
    title: str
    slug: str
    description: str
    tags: list[str] = Field(default_factory=list)
    markdown: str
    metadata: dict = Field(default_factory=dict)
    created_by: RevisionAuthor = RevisionAuthor.AI
    content_hash: str
    created_at: datetime | None = None


class EvaluationResultEntity(BaseModel):
    id: uuid.UUID | None = None
    revision_id: uuid.UUID
    kind: str                    # deterministic | judge
    passed: bool
    scores: dict = Field(default_factory=dict)
    issues: list[ValidationIssue] = Field(default_factory=list)
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime | None = None


class StyleGuideEntity(BaseModel):
    id: uuid.UUID | None = None
    version: str
    content: str
    created_by: str = "owner"
    created_at: datetime | None = None
