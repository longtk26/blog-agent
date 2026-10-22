import uuid
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, select

from src.libs.database.session import SessionDep
from src.modules.research.ports.output.brief_repository import IBriefRepository
from src.modules.shared.domain.entities import ResearchBriefEntity
from src.modules.shared.infrastructure.models import ResearchBriefModel
from src.modules.shared.infrastructure.models._columns import utcnow


class BriefRepository(IBriefRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def upsert(self, brief: ResearchBriefEntity) -> ResearchBriefEntity:
        model = self.session.exec(
            select(ResearchBriefModel).where(ResearchBriefModel.task_id == brief.task_id)
        ).first()
        if model is None:
            model = ResearchBriefModel(task_id=brief.task_id, markdown=brief.markdown, data=brief.data)
        else:
            model.markdown = brief.markdown
            model.data = brief.data
            model.created_at = utcnow()
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def get_by_task(self, task_id: uuid.UUID) -> ResearchBriefEntity | None:
        model = self.session.exec(select(ResearchBriefModel).where(ResearchBriefModel.task_id == task_id)).first()
        return self.__to_entity(model) if model else None

    def __to_entity(self, model: ResearchBriefModel) -> ResearchBriefEntity:
        return ResearchBriefEntity(
            id=model.id, task_id=model.task_id, markdown=model.markdown, data=model.data or {}, created_at=model.created_at
        )


IBriefRepoDep = Annotated[IBriefRepository, Depends(BriefRepository)]
