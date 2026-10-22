from typing import Annotated

from fastapi import Depends
from sqlalchemy import func
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.shared.domain.entities import StyleGuideEntity
from src.modules.shared.infrastructure.models import StyleGuideModel
from src.modules.styles.ports.output.style_guide_repository import IStyleGuideRepository


class StyleGuideRepository(IStyleGuideRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def latest(self) -> StyleGuideEntity | None:
        statement = select(StyleGuideModel).order_by(col(StyleGuideModel.created_at).desc()).limit(1)
        model = self.session.exec(statement).first()
        return self.__to_entity(model) if model else None

    def create(self, guide: StyleGuideEntity) -> StyleGuideEntity:
        model = StyleGuideModel(version=guide.version, content=guide.content, created_by=guide.created_by)
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def count(self) -> int:
        return self.session.exec(select(func.count()).select_from(StyleGuideModel)).one()

    def __to_entity(self, model: StyleGuideModel) -> StyleGuideEntity:
        return StyleGuideEntity(
            id=model.id, version=model.version, content=model.content, created_by=model.created_by, created_at=model.created_at
        )


IStyleGuideRepoDep = Annotated[IStyleGuideRepository, Depends(StyleGuideRepository)]
