import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .writing_task_entity import PublicationTarget


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    SUPERSEDED = "superseded"   # a newer revision exists; the approval no longer unlocks publishing


class ApprovalEntity(BaseModel):
    """The owner's approval of one exact revision (by content hash) for one destination."""

    id: uuid.UUID | None = None
    task_id: uuid.UUID
    article_revision_id: uuid.UUID
    content_hash: str
    destination: PublicationTarget
    options: dict = Field(default_factory=dict)
    decision: ApprovalDecision = ApprovalDecision.APPROVED
    reviewer_id: str = "owner"
    reviewed_at: datetime | None = None
    superseded_at: datetime | None = None
