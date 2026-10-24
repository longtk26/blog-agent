import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import ApprovalEntity, PublicationTarget


class IApprovalRepository(ABC):
    @abstractmethod
    def add_many(self, approvals: list[ApprovalEntity]) -> list[ApprovalEntity]:
        pass

    @abstractmethod
    def list_by_task(self, task_id: uuid.UUID) -> list[ApprovalEntity]:
        pass

    @abstractmethod
    def get_live(self, revision_id: uuid.UUID, destination: PublicationTarget) -> ApprovalEntity | None:
        """The non-superseded approval for this revision and destination, if any."""
        pass

    @abstractmethod
    def supersede_for_task(self, task_id: uuid.UUID, keep_revision_id: uuid.UUID | None = None) -> int:
        """Mark live approvals of the task's other revisions as superseded; returns how many changed."""
        pass
