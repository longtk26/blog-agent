import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, text
from sqlmodel import Column, Field, SQLModel

from ._columns import jsonb_column, timestamp_column, utcnow


class ApprovalModel(SQLModel, table=True):
    """One row per (revision, destination). Only `decision`/`superseded_at` ever change (approved -> superseded)."""

    __tablename__ = "approvals"
    __table_args__ = (
        # At most one live approval per revision and destination.
        Index(
            "uq_approvals_live",
            "article_revision_id",
            "destination",
            unique=True,
            postgresql_where=text("decision = 'approved'"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    article_revision_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("article_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    content_hash: str = Field(max_length=64)
    destination: str = Field(max_length=16)
    options: dict = Field(default_factory=dict, sa_column=jsonb_column())
    decision: str = Field(max_length=16)
    reviewer_id: str = Field(default="owner", max_length=64)
    reviewed_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    superseded_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
