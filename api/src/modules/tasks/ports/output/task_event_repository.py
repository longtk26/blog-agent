import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import TaskEventEntity


class ITaskEventRepository(ABC):
    @abstractmethod
    def add(self, event: TaskEventEntity) -> TaskEventEntity:
        pass

    @abstractmethod
    def list_after(self, task_id: uuid.UUID, after_id: int = 0, limit: int = 500) -> list[TaskEventEntity]:
        pass
