from typing import Annotated
import uuid

from fastapi import Depends
from sqlalchemy import func
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.shared.domain.entities import WritingSampleEntity
from src.modules.shared.infrastructure.models import WritingSampleModel
from src.modules.shared.infrastructure.models._columns import utcnow
from src.modules.styles.ports.output.writing_sample_repository import IWritingSampleRepository


class WritingSampleRepository(IWritingSampleRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def create(self, sample: WritingSampleEntity) -> WritingSampleEntity:
        model = WritingSampleModel(
            id=sample.id,
            origin=sample.origin,
            remote_id=sample.remote_id,
            title=sample.title,
            tags=sample.tags,
            published_at=sample.published_at,
            approved_as_style_example=sample.approved_as_style_example,
            content=sample.content,
            content_hash=sample.content_hash,
            created_at=sample.created_at or utcnow(),
            updated_at=sample.updated_at or utcnow(),
        )
        self.session.add(model)
        self.session.flush()
        return self._to_entity(model)

    def update(self, sample: WritingSampleEntity) -> WritingSampleEntity:
        model = self.session.get(WritingSampleModel, sample.id)
        if not model:
            raise KeyError(f"Writing sample not found: {sample.id}")
        model.title = sample.title
        model.tags = sample.tags
        model.published_at = sample.published_at
        model.approved_as_style_example = sample.approved_as_style_example
        model.content = sample.content
        model.content_hash = sample.content_hash
        model.updated_at = utcnow()
        self.session.add(model)
        self.session.flush()
        return self._to_entity(model)

    def get(self, sample_id: uuid.UUID) -> WritingSampleEntity | None:
        model = self.session.get(WritingSampleModel, sample_id)
        return self._to_entity(model) if model else None

    def get_by_origin_and_remote(self, origin: str, remote_id: str) -> WritingSampleEntity | None:
        statement = (
            select(WritingSampleModel)
            .where(WritingSampleModel.origin == origin)
            .where(WritingSampleModel.remote_id == remote_id)
        )
        model = self.session.exec(statement).first()
        return self._to_entity(model) if model else None

    def list_all(self, approved_only: bool = False) -> list[WritingSampleEntity]:
        stmt = select(WritingSampleModel)
        if approved_only:
            stmt = stmt.where(WritingSampleModel.approved_as_style_example.is_(True))
        stmt = stmt.order_by(col(WritingSampleModel.published_at).desc().nullslast(), col(WritingSampleModel.created_at).desc())
        models = self.session.exec(stmt).all()
        return [self._to_entity(m) for m in models]

    def count(self) -> int:
        return self.session.exec(select(func.count()).select_from(WritingSampleModel)).one()

    def get_sanity_post_ids(self) -> set[str]:
        stmt = select(WritingSampleModel.remote_id).where(WritingSampleModel.origin == "sanity")
        return set(self.session.exec(stmt).all())

    def delete(self, sample_id: uuid.UUID) -> bool:
        model = self.session.get(WritingSampleModel, sample_id)
        if not model:
            return False
        self.session.delete(model)
        self.session.flush()
        return True

    @staticmethod
    def _to_entity(model: WritingSampleModel) -> WritingSampleEntity:
        return WritingSampleEntity(
            id=model.id,
            origin=model.origin,
            remote_id=model.remote_id,
            title=model.title,
            tags=list(model.tags or []),
            published_at=model.published_at,
            approved_as_style_example=model.approved_as_style_example,
            content=model.content,
            content_hash=model.content_hash,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


IWritingSampleRepoDep = Annotated[IWritingSampleRepository, Depends(WritingSampleRepository)]
