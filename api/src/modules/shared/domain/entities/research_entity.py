import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    OFFICIAL_DOCS = "official_docs"
    PAPER = "paper"
    REPOSITORY = "repository"
    REPUTABLE_PUBLICATION = "reputable_publication"
    BLOG = "blog"
    FORUM = "forum"
    OTHER = "other"


class SourceStatus(StrEnum):
    PENDING = "pending"          # found by search, not fetched yet
    EXTRACTED = "extracted"      # page text stored
    ASSESSED = "assessed"        # notes + claims produced
    LOW_QUALITY = "low_quality"  # assessed but below the quality threshold
    FAILED = "failed"            # fetch/extract failed


class ResearchSourceEntity(BaseModel):
    id: uuid.UUID | None = None
    task_id: uuid.UUID
    url: str
    canonical_url: str
    title: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    retrieved_at: datetime | None = None
    snippet: str | None = None
    query: str | None = None
    round: int = 1
    status: SourceStatus = SourceStatus.PENDING
    content_text: str | None = None
    content_hash: str | None = None
    source_type: SourceType | None = None
    quality_score: float | None = None
    quality_rationale: str | None = None
    relevance: float | None = None
    notes: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime | None = None


class ResearchClaimEntity(BaseModel):
    id: uuid.UUID | None = None
    task_id: uuid.UUID
    source_id: uuid.UUID
    question_id: str | None = None
    text: str
    supporting_quote: str
    quote_verified: bool = False
    created_at: datetime | None = None


class ResearchBriefEntity(BaseModel):
    id: uuid.UUID | None = None
    task_id: uuid.UUID
    markdown: str
    data: dict = Field(default_factory=dict)
    created_at: datetime | None = None
