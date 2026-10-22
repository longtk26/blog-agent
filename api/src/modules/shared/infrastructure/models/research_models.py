import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Text, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from ._columns import jsonb_column, timestamp_column, utcnow


class ResearchSourceModel(SQLModel, table=True):
    __tablename__ = "research_sources"
    __table_args__ = (UniqueConstraint("task_id", "canonical_url", name="uq_research_sources_task_url"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    url: str = Field(sa_column=Column(Text, nullable=False))
    canonical_url: str = Field(sa_column=Column(Text, nullable=False))
    title: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    publisher: str | None = Field(default=None, max_length=200)
    published_at: str | None = Field(default=None, max_length=64)
    retrieved_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    snippet: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    query: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    round: int = 1
    status: str = Field(max_length=16, index=True)
    content_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    content_hash: str | None = Field(default=None, max_length=64)
    source_type: str | None = Field(default=None, max_length=32)
    quality_score: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    quality_rationale: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    relevance: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    notes: list = Field(default_factory=list, sa_column=jsonb_column())
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class ResearchClaimModel(SQLModel, table=True):
    __tablename__ = "research_claims"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    source_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    question_id: str | None = Field(default=None, max_length=32)
    text: str = Field(sa_column=Column(Text, nullable=False))
    supporting_quote: str = Field(sa_column=Column(Text, nullable=False))
    quote_verified: bool = False
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class ResearchBriefModel(SQLModel, table=True):
    __tablename__ = "research_briefs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, unique=True)
    )
    markdown: str = Field(sa_column=Column(Text, nullable=False))
    data: dict = Field(default_factory=dict, sa_column=jsonb_column())
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
