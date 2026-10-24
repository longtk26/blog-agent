from typing import Annotated
import uuid

from fastapi import Depends
from sqlalchemy import func
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.shared.domain.entities import StyleProfileEntity
from src.modules.shared.infrastructure.models import StyleProfileModel
from src.modules.shared.infrastructure.models._columns import utcnow
from src.modules.styles.ports.output.style_profile_repository import IStyleProfileRepository


class StyleProfileRepository(IStyleProfileRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def get_active(self) -> StyleProfileEntity | None:
        statement = select(StyleProfileModel).where(StyleProfileModel.is_active.is_(True)).limit(1)
        model = self.session.exec(statement).first()
        return self._to_entity(model) if model else None

    def get_by_version(self, version: int) -> StyleProfileEntity | None:
        statement = select(StyleProfileModel).where(StyleProfileModel.version == version).limit(1)
        model = self.session.exec(statement).first()
        return self._to_entity(model) if model else None

    def get_by_id(self, profile_id: uuid.UUID) -> StyleProfileEntity | None:
        model = self.session.get(StyleProfileModel, profile_id)
        return self._to_entity(model) if model else None

    def list_all(self) -> list[StyleProfileEntity]:
        statement = select(StyleProfileModel).order_by(col(StyleProfileModel.version).desc())
        models = self.session.exec(statement).all()
        return [self._to_entity(m) for m in models]

    def latest_version(self) -> int:
        statement = select(func.max(StyleProfileModel.version))
        res = self.session.exec(statement).one_or_none()
        return res if res is not None else 0

    def create(self, profile: StyleProfileEntity) -> StyleProfileEntity:
        if profile.is_active:
            # Deactivate all existing profiles
            existing = self.session.exec(select(StyleProfileModel).where(StyleProfileModel.is_active.is_(True))).all()
            for p in existing:
                p.is_active = False
                self.session.add(p)

        model = StyleProfileModel(
            id=profile.id,
            version=profile.version,
            is_active=profile.is_active,
            name=profile.name,
            profile_data=profile.profile_data,
            markdown_content=profile.markdown_content,
            created_at=profile.created_at or utcnow(),
            updated_at=profile.updated_at or utcnow(),
        )
        self.session.add(model)
        self.session.flush()
        return self._to_entity(model)

    def activate(self, profile_id: uuid.UUID) -> StyleProfileEntity | None:
        target = self.session.get(StyleProfileModel, profile_id)
        if not target:
            return None

        # Deactivate all
        existing = self.session.exec(select(StyleProfileModel).where(StyleProfileModel.is_active.is_(True))).all()
        for p in existing:
            p.is_active = False
            self.session.add(p)

        target.is_active = True
        target.updated_at = utcnow()
        self.session.add(target)
        self.session.flush()
        return self._to_entity(target)

    @staticmethod
    def _to_entity(model: StyleProfileModel) -> StyleProfileEntity:
        return StyleProfileEntity(
            id=model.id,
            version=model.version,
            is_active=model.is_active,
            name=model.name,
            profile_data=dict(model.profile_data or {}),
            markdown_content=model.markdown_content,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


IStyleProfileRepoDep = Annotated[IStyleProfileRepository, Depends(StyleProfileRepository)]
