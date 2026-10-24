import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from .writing_task_entity import PublicationTarget


class PublicationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PublicationEntity(BaseModel):
    id: uuid.UUID | None = None
    task_id: uuid.UUID
    article_revision_id: uuid.UUID
    destination: PublicationTarget | str
    remote_document_id: str | None = None
    remote_url: str | None = None
    status: PublicationStatus = PublicationStatus.PENDING
    attempt_count: int = 0
    rendered_content_hash: str | None = None
    last_error: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
