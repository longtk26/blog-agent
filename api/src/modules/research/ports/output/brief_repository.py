import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import ResearchBriefEntity


class IBriefRepository(ABC):
    @abstractmethod
    def upsert(self, brief: ResearchBriefEntity) -> ResearchBriefEntity:
        pass

    @abstractmethod
    def get_by_task(self, task_id: uuid.UUID) -> ResearchBriefEntity | None:
        pass
