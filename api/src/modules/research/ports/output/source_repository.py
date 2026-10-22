import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import ResearchSourceEntity, SourceStatus


class ISourceRepository(ABC):
    @abstractmethod
    def add_if_new(self, source: ResearchSourceEntity) -> ResearchSourceEntity | None:
        """Insert unless (task_id, canonical_url) already exists; returns None for duplicates."""
        pass

    @abstractmethod
    def get(self, source_id: uuid.UUID) -> ResearchSourceEntity | None:
        pass

    @abstractmethod
    def update(self, source: ResearchSourceEntity) -> ResearchSourceEntity:
        pass

    @abstractmethod
    def list_by_task(
        self, task_id: uuid.UUID, statuses: list[SourceStatus] | None = None, include_content: bool = False
    ) -> list[ResearchSourceEntity]:
        pass

    @abstractmethod
    def canonical_urls(self, task_id: uuid.UUID) -> set[str]:
        pass

    @abstractmethod
    def count_by_status(self, task_id: uuid.UUID) -> dict[str, int]:
        pass
