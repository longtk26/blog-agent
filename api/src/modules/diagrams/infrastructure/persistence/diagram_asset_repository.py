"""SQLModel implementation of IDiagramAssetRepository (E7-S6)."""

import uuid
from typing import Annotated
from fastapi import Depends
from sqlmodel import Session, select

from src.libs.database import SessionDep
from src.modules.diagrams.ports.output.diagram_repository import IDiagramAssetRepository
from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity
from src.modules.shared.infrastructure.models.diagram_models import DiagramAssetModel


class DiagramAssetRepository(IDiagramAssetRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def create(self, asset: DiagramAssetEntity) -> DiagramAssetEntity:
        model = self.__to_model(asset)
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def get(self, asset_id: uuid.UUID) -> DiagramAssetEntity | None:
        model = self.session.get(DiagramAssetModel, asset_id)
        return self.__to_entity(model) if model else None

    def get_by_slot(self, task_id: uuid.UUID, slot_id: str) -> DiagramAssetEntity | None:
        statement = select(DiagramAssetModel).where(
            DiagramAssetModel.task_id == task_id,
            DiagramAssetModel.slot_id == slot_id,
        ).order_by(DiagramAssetModel.created_at.desc())
        model = self.session.exec(statement).first()
        return self.__to_entity(model) if model else None

    def list_by_task(self, task_id: uuid.UUID) -> list[DiagramAssetEntity]:
        statement = select(DiagramAssetModel).where(
            DiagramAssetModel.task_id == task_id
        ).order_by(DiagramAssetModel.created_at.asc())
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def list_by_revision(self, revision_id: uuid.UUID) -> list[DiagramAssetEntity]:
        statement = select(DiagramAssetModel).where(
            DiagramAssetModel.article_revision_id == revision_id
        ).order_by(DiagramAssetModel.created_at.asc())
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def update(self, asset: DiagramAssetEntity) -> DiagramAssetEntity:
        model = self.session.get(DiagramAssetModel, asset.id)
        if not model:
            raise KeyError(f"Diagram asset not found: {asset.id}")
        fresh = self.__to_model(asset)
        for field in DiagramAssetModel.model_fields:
            if field not in ("id", "created_at"):
                setattr(model, field, getattr(fresh, field))
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def delete(self, asset_id: uuid.UUID) -> None:
        model = self.session.get(DiagramAssetModel, asset_id)
        if model:
            self.session.delete(model)
            self.session.flush()

    @staticmethod
    def __to_model(entity: DiagramAssetEntity) -> DiagramAssetModel:
        return DiagramAssetModel(
            id=entity.id,
            task_id=entity.task_id,
            article_revision_id=entity.article_revision_id,
            slot_id=entity.slot_id,
            format=entity.format,
            spec=entity.spec,
            source_path=entity.source_path,
            svg_path=entity.svg_path,
            png_path=entity.png_path,
            sha256=entity.sha256,
            validation_status=entity.validation_status,
            created_at=entity.created_at,
        )

    @staticmethod
    def __to_entity(model: DiagramAssetModel) -> DiagramAssetEntity:
        return DiagramAssetEntity(
            id=model.id,
            task_id=model.task_id,
            article_revision_id=model.article_revision_id,
            slot_id=model.slot_id,
            format=model.format,
            spec=model.spec,
            source_path=model.source_path,
            svg_path=model.svg_path,
            png_path=model.png_path,
            sha256=model.sha256,
            validation_status=model.validation_status,
            created_at=model.created_at,
        )


DiagramAssetRepositoryDep = Annotated[IDiagramAssetRepository, Depends(DiagramAssetRepository)]
