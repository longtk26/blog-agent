import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import TaskEventEntity
from src.modules.shared.domain.value_objects import TaskStatus


class ITaskEventFeed(ABC):
    """Async, request-independent reads for long-lived event streams (SSE)."""

    @abstractmethod
    async def events_after(self, task_id: uuid.UUID, after_id: int) -> list[TaskEventEntity]:
        pass

    @abstractmethod
    async def status(self, task_id: uuid.UUID) -> TaskStatus | None:
        pass
