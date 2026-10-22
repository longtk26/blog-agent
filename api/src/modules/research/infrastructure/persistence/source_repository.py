import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import defer
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.research.ports.output.source_repository import ISourceRepository
from src.modules.shared.domain.entities import ResearchSourceEntity, SourceStatus
from src.modules.shared.infrastructure.models import ResearchSourceModel


class SourceRepository(ISourceRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def add_if_new(self, source: ResearchSourceEntity) -> ResearchSourceEntity | None:
        values = self.__to_model(source).model_dump()
        statement = (
            insert(ResearchSourceModel)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_research_sources_task_url")
            .returning(ResearchSourceModel.id)
        )
        inserted_id = self.session.exec(statement).scalar_one_or_none()
        if inserted_id is None:
            return None
        return self.get(inserted_id)

    def get(self, source_id: uuid.UUID) -> ResearchSourceEntity | None:
        model = self.session.get(ResearchSourceModel, source_id)
        return self.__to_entity(model, include_content=True) if model else None

    def update(self, source: ResearchSourceEntity) -> ResearchSourceEntity:
        model = self.session.get(ResearchSourceModel, source.id)
        fresh = self.__to_model(source)
        for field in ResearchSourceModel.model_fields:
            if field in ("id", "task_id", "created_at"):
                continue
            # Entities listed without content carry content_text=None; never let that wipe stored text.
            if field in ("content_text", "content_hash") and getattr(fresh, field) is None:
                continue
            setattr(model, field, getattr(fresh, field))
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model, include_content=True)

    def list_by_task(
        self, task_id: uuid.UUID, statuses: list[SourceStatus] | None = None, include_content: bool = False
    ) -> list[ResearchSourceEntity]:
        statement = select(ResearchSourceModel).where(ResearchSourceModel.task_id == task_id)
        if not include_content:
            statement = statement.options(defer(ResearchSourceModel.content_text))
        if statuses:
            statement = statement.where(col(ResearchSourceModel.status).in_([str(s) for s in statuses]))
        statement = statement.order_by(col(ResearchSourceModel.created_at), col(ResearchSourceModel.id))
        return [self.__to_entity(m, include_content) for m in self.session.exec(statement).all()]

    def canonical_urls(self, task_id: uuid.UUID) -> set[str]:
        statement = select(ResearchSourceModel.canonical_url).where(ResearchSourceModel.task_id == task_id)
        return set(self.session.exec(statement).all())

    def count_by_status(self, task_id: uuid.UUID) -> dict[str, int]:
        statement = (
            select(ResearchSourceModel.status, func.count())
            .where(ResearchSourceModel.task_id == task_id)
            .group_by(ResearchSourceModel.status)
        )
        return {status: count for status, count in self.session.exec(statement).all()}

    def __to_entity(self, model: ResearchSourceModel, include_content: bool) -> ResearchSourceEntity:
        return ResearchSourceEntity(
            id=model.id,
            task_id=model.task_id,
            url=model.url,
            canonical_url=model.canonical_url,
            title=model.title,
            publisher=model.publisher,
            published_at=model.published_at,
            retrieved_at=model.retrieved_at,
            snippet=model.snippet,
            query=model.query,
            round=model.round,
            status=model.status,
            content_text=model.content_text if include_content else None,
            content_hash=model.content_hash,
            source_type=model.source_type,
            quality_score=model.quality_score,
            quality_rationale=model.quality_rationale,
            relevance=model.relevance,
            notes=model.notes or [],
            error=model.error,
            created_at=model.created_at,
        )

    def __to_model(self, entity: ResearchSourceEntity) -> ResearchSourceModel:
        data = entity.model_dump(mode="json", exclude={"id", "created_at", "retrieved_at", "task_id"})
        model = ResearchSourceModel(**data, task_id=entity.task_id, retrieved_at=entity.retrieved_at)
        if entity.id is not None:
            model.id = entity.id
        return model


ISourceRepoDep = Annotated[ISourceRepository, Depends(SourceRepository)]
