import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import PublicationEntity, PublicationTarget


class IPublicationRepository(ABC):
    @abstractmethod
    def get(self, publication_id: uuid.UUID) -> PublicationEntity | None:
        """Get publication by its ID."""
        ...

    @abstractmethod
    def get_by_task_and_destination(
        self, task_id: uuid.UUID, destination: PublicationTarget | str
    ) -> PublicationEntity | None:
        """Get publication by task_id and destination."""
        ...

    @abstractmethod
    def list_by_task(self, task_id: uuid.UUID) -> list[PublicationEntity]:
        """List all publications for a task."""
        ...

    @abstractmethod
    def save(self, publication: PublicationEntity) -> PublicationEntity:
        """Create or update a publication."""
        ...

    @abstractmethod
    def delete(self, publication_id: uuid.UUID) -> None:
        """Delete a publication record."""
        ...
