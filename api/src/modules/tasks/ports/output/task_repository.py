import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import WritingTaskEntity
from src.modules.shared.domain.value_objects import TaskStatus


class ITaskRepository(ABC):
    @abstractmethod
    def create(self, task: WritingTaskEntity) -> WritingTaskEntity:
        pass

    @abstractmethod
    def get(self, task_id: uuid.UUID, for_update: bool = False) -> WritingTaskEntity | None:
        pass

    @abstractmethod
    def update(self, task: WritingTaskEntity) -> WritingTaskEntity:
        pass

    @abstractmethod
    def list_page(
        self,
        statuses: list[TaskStatus] | None = None,
        mode: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[WritingTaskEntity], int]:
        pass

    @abstractmethod
    def list_by_statuses(self, statuses: list[TaskStatus]) -> list[WritingTaskEntity]:
        pass
