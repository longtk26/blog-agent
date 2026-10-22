import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from ._columns import jsonb_column, timestamp_column, utcnow


class ArticleDraftModel(SQLModel, table=True):
    __tablename__ = "article_drafts"

    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), primary_key=True)
    )
    sections: list = Field(default_factory=list, sa_column=jsonb_column())
    article_metadata: dict | None = Field(default=None, sa_column=jsonb_column(nullable=True))
    markdown: str = Field(default="", sa_column=Column(Text, nullable=False))
    issues: list = Field(default_factory=list, sa_column=jsonb_column())
    judge: dict | None = Field(default=None, sa_column=jsonb_column(nullable=True))
    self_revisions: int = 0
    history: list = Field(default_factory=list, sa_column=jsonb_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class ArticleRevisionModel(SQLModel, table=True):
    """Immutable: a DB trigger rejects UPDATE (migration 0003)."""

    __tablename__ = "article_revisions"
    __table_args__ = (UniqueConstraint("task_id", "revision_number", name="uq_article_revisions_task_number"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    revision_number: int = Field(sa_column=Column(Integer, nullable=False))
    parent_revision_id: uuid.UUID | None = Field(
        default=None, sa_column=Column(ForeignKey("article_revisions.id"), nullable=True)
    )
    title: str = Field(sa_column=Column(Text, nullable=False))
    slug: str = Field(max_length=80, index=True)
    description: str = Field(sa_column=Column(Text, nullable=False))
    tags: list = Field(default_factory=list, sa_column=jsonb_column())
    markdown: str = Field(sa_column=Column(Text, nullable=False))
    revision_metadata: dict = Field(default_factory=dict, sa_column=jsonb_column())
    created_by: str = Field(max_length=16)
    content_hash: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class EvaluationResultModel(SQLModel, table=True):
    __tablename__ = "evaluation_results"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    revision_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("article_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    kind: str = Field(max_length=32)
    passed: bool
    scores: dict = Field(default_factory=dict, sa_column=jsonb_column())
    issues: list = Field(default_factory=list, sa_column=jsonb_column())
    model: str | None = Field(default=None, max_length=120)
    prompt_version: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class StyleGuideModel(SQLModel, table=True):
    __tablename__ = "style_guides"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version: str = Field(max_length=64, unique=True)
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_by: str = Field(default="owner", max_length=16)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
