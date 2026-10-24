import uuid
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, col, select, update

from src.libs.database.session import SessionDep
from src.modules.reviews.ports.output.approval_repository import IApprovalRepository
from src.modules.shared.domain.entities import ApprovalDecision, ApprovalEntity, PublicationTarget
from src.modules.shared.infrastructure.models import ApprovalModel
from src.modules.shared.infrastructure.models._columns import utcnow


class ApprovalRepository(IApprovalRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def add_many(self, approvals: list[ApprovalEntity]) -> list[ApprovalEntity]:
        models = [
            ApprovalModel(**approval.model_dump(mode="json", exclude={"id", "reviewed_at", "superseded_at", "task_id", "article_revision_id"}),
                          task_id=approval.task_id, article_revision_id=approval.article_revision_id)
            for approval in approvals
        ]
        self.session.add_all(models)
        self.session.flush()
        return [self.__to_entity(m) for m in models]

    def list_by_task(self, task_id: uuid.UUID) -> list[ApprovalEntity]:
        statement = (
            select(ApprovalModel).where(ApprovalModel.task_id == task_id).order_by(col(ApprovalModel.reviewed_at).desc())
        )
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def get_live(self, revision_id: uuid.UUID, destination: PublicationTarget) -> ApprovalEntity | None:
        statement = select(ApprovalModel).where(
            ApprovalModel.article_revision_id == revision_id,
            ApprovalModel.destination == str(destination),
            ApprovalModel.decision == ApprovalDecision.APPROVED.value,
        )
        model = self.session.exec(statement).first()
        return self.__to_entity(model) if model else None

    def supersede_for_task(self, task_id: uuid.UUID, keep_revision_id: uuid.UUID | None = None) -> int:
        conditions = [ApprovalModel.task_id == task_id, ApprovalModel.decision == ApprovalDecision.APPROVED.value]
        if keep_revision_id is not None:
            conditions.append(ApprovalModel.article_revision_id != keep_revision_id)
        result = self.session.exec(
            update(ApprovalModel)
            .where(*conditions)
            .values(decision=ApprovalDecision.SUPERSEDED.value, superseded_at=utcnow())
        )
        self.session.flush()
        return result.rowcount or 0

    def __to_entity(self, model: ApprovalModel) -> ApprovalEntity:
        return ApprovalEntity(
            id=model.id,
            task_id=model.task_id,
            article_revision_id=model.article_revision_id,
            content_hash=model.content_hash,
            destination=model.destination,
            options=model.options or {},
            decision=model.decision,
            reviewer_id=model.reviewer_id,
            reviewed_at=model.reviewed_at,
            superseded_at=model.superseded_at,
        )


IApprovalRepoDep = Annotated[IApprovalRepository, Depends(ApprovalRepository)]
