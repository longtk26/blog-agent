import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import ResearchClaimEntity


class IClaimRepository(ABC):
    @abstractmethod
    def replace_for_source(self, source_id: uuid.UUID, claims: list[ResearchClaimEntity]) -> list[ResearchClaimEntity]:
        """Idempotent per source: re-assessing a source replaces its claims."""
        pass

    @abstractmethod
    def list_by_task(self, task_id: uuid.UUID) -> list[ResearchClaimEntity]:
        pass

    @abstractmethod
    def count_by_task(self, task_id: uuid.UUID) -> int:
        pass
