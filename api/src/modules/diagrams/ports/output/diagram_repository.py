"""Output port for diagram asset persistence (E7-S6)."""

from abc import ABC, abstractmethod
import uuid

from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity


class IDiagramAssetRepository(ABC):
    @abstractmethod
    def create(self, asset: DiagramAssetEntity) -> DiagramAssetEntity:
        ...

    @abstractmethod
    def get(self, asset_id: uuid.UUID) -> DiagramAssetEntity | None:
        ...

    @abstractmethod
    def get_by_slot(self, task_id: uuid.UUID, slot_id: str) -> DiagramAssetEntity | None:
        ...

    @abstractmethod
    def list_by_task(self, task_id: uuid.UUID) -> list[DiagramAssetEntity]:
        ...

    @abstractmethod
    def list_by_revision(self, revision_id: uuid.UUID) -> list[DiagramAssetEntity]:
        ...

    @abstractmethod
    def update(self, asset: DiagramAssetEntity) -> DiagramAssetEntity:
        ...

    @abstractmethod
    def delete(self, asset_id: uuid.UUID) -> None:
        ...
