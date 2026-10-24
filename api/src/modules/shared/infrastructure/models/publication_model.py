import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, Text
from sqlmodel import AutoString, Field, SQLModel

from ._columns import timestamp_column


class PublicationModel(SQLModel, table=True):
    """One row per (task_id, destination). Stored on the first publish and updated on later revisions."""

    __tablename__ = "publications"
    __table_args__ = (
        Index("uq_publications_task_destination", "task_id", "destination", unique=True),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    article_revision_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("article_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    destination: str = Field(sa_column=Column(AutoString(16), nullable=False))
    remote_document_id: str | None = Field(default=None, sa_column=Column(AutoString(128), nullable=True))
    remote_url: str | None = Field(default=None, sa_column=Column(AutoString(512), nullable=True))
    status: str = Field(default="pending", sa_column=Column(AutoString(16), nullable=False))
    attempt_count: int = Field(default=0)
    rendered_content_hash: str | None = Field(default=None, sa_column=Column(AutoString(64), nullable=True))
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    published_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    updated_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
