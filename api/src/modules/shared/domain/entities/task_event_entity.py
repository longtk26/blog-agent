import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EventActor(StrEnum):
    SYSTEM = "system"
    OWNER = "owner"
    AGENT = "agent"


class TaskEventEntity(BaseModel):
    id: int | None = None
    task_id: uuid.UUID
    type: str
    from_status: str | None = None
    to_status: str | None = None
    actor: EventActor = EventActor.SYSTEM
    payload: dict = Field(default_factory=dict)
    created_at: datetime | None = None
