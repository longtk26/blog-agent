import uuid
from typing import Annotated
from fastapi import Depends

from src.libs.exceptions import NotFoundException
from src.modules.articles.ports.output import IEvaluationRepoDep, IRevisionRepoDep
from src.modules.articles.presenter.dtos import RevisionListResponseDto, RevisionResponseDto, RevisionSummaryDto
from src.modules.reviews.ports.output import IApprovalRepoDep
from src.modules.tasks.ports.output import ITaskRepoDep


class ListRevisionsUsecase():
    def __init__(
        self, tasks: ITaskRepoDep, revisions: IRevisionRepoDep, evaluations: IEvaluationRepoDep, approvals: IApprovalRepoDep
    ):
        self.tasks = tasks
        self.revisions = revisions
        self.evaluations = evaluations
        self.approvals = approvals

    async def execute(self, task_id: uuid.UUID) -> RevisionListResponseDto:
        if self.tasks.get(task_id) is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        approvals = self.approvals.list_by_task(task_id)
        items = [
            RevisionSummaryDto.from_entity(revision, self.evaluations.list_by_revision(revision.id), approvals)
            for revision in self.revisions.list_by_task(task_id)
        ]
        return RevisionListResponseDto(items=items)


class GetRevisionUsecase():
    def __init__(self, revisions: IRevisionRepoDep, evaluations: IEvaluationRepoDep):
        self.revisions = revisions
        self.evaluations = evaluations

    async def execute(self, revision_id: uuid.UUID) -> RevisionResponseDto:
        revision = self.revisions.get(revision_id)
        if revision is None:
            raise NotFoundException(f"Revision '{revision_id}' not found")
        return RevisionResponseDto.from_entity(revision, self.evaluations.list_by_revision(revision_id))


ListRevisionsUsecaseDep = Annotated[ListRevisionsUsecase, Depends(ListRevisionsUsecase)]
GetRevisionUsecaseDep = Annotated[GetRevisionUsecase, Depends(GetRevisionUsecase)]
