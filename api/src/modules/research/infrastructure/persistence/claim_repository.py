import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.research.ports.output.claim_repository import IClaimRepository
from src.modules.shared.domain.entities import ResearchClaimEntity
from src.modules.shared.infrastructure.models import ResearchClaimModel


class ClaimRepository(IClaimRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def replace_for_source(self, source_id: uuid.UUID, claims: list[ResearchClaimEntity]) -> list[ResearchClaimEntity]:
        self.session.exec(delete(ResearchClaimModel).where(col(ResearchClaimModel.source_id) == source_id))
        models = [self.__to_model(claim) for claim in claims]
        self.session.add_all(models)
        self.session.flush()
        return [self.__to_entity(m) for m in models]

    def list_by_task(self, task_id: uuid.UUID) -> list[ResearchClaimEntity]:
        statement = (
            select(ResearchClaimModel)
            .where(ResearchClaimModel.task_id == task_id)
            .order_by(col(ResearchClaimModel.created_at), col(ResearchClaimModel.id))
        )
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def count_by_task(self, task_id: uuid.UUID) -> int:
        statement = select(func.count()).select_from(ResearchClaimModel).where(ResearchClaimModel.task_id == task_id)
        return self.session.exec(statement).one()

    def __to_entity(self, model: ResearchClaimModel) -> ResearchClaimEntity:
        return ResearchClaimEntity(
            id=model.id,
            task_id=model.task_id,
            source_id=model.source_id,
            question_id=model.question_id,
            text=model.text,
            supporting_quote=model.supporting_quote,
            quote_verified=model.quote_verified,
            created_at=model.created_at,
        )

    def __to_model(self, entity: ResearchClaimEntity) -> ResearchClaimModel:
        model = ResearchClaimModel(
            task_id=entity.task_id,
            source_id=entity.source_id,
            question_id=entity.question_id,
            text=entity.text,
            supporting_quote=entity.supporting_quote,
            quote_verified=entity.quote_verified,
        )
        if entity.id is not None:
            model.id = entity.id
        return model


IClaimRepoDep = Annotated[IClaimRepository, Depends(ClaimRepository)]
