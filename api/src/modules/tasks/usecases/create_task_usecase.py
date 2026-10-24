import uuid
from typing import Annotated
from fastapi import Depends

from src.libs.decorators.transactional_decorator import Transactional
from src.libs.events import EventBrokerDep
from src.libs.exceptions import BadRequestException, NotFoundException
from src.modules.agent.ports.output import IWorkflowRunnerDep
from src.modules.research.ports.output import IClaimRepoDep, ISourceRepoDep
from src.modules.shared.domain.entities import EventActor, SourceStatus, TaskEventEntity, WritingTaskEntity
from src.modules.tasks.ports.output import ITaskEventRepoDep, ITaskRepoDep
from src.modules.tasks.presenter.dtos import CreateTaskRequestDto, TaskResponseDto

REUSABLE = [SourceStatus.ASSESSED, SourceStatus.LOW_QUALITY]


class CreateTaskUsecase():
    def __init__(
        self,
        tasks: ITaskRepoDep,
        events: ITaskEventRepoDep,
        sources: ISourceRepoDep,
        claims: IClaimRepoDep,
        runner: IWorkflowRunnerDep,
        broker: EventBrokerDep,
    ):
        self.tasks = tasks
        self.events = events
        self.sources = sources
        self.claims = claims
        self.runner = runner
        self.broker = broker

    async def execute(self, dto: CreateTaskRequestDto) -> TaskResponseDto:
        if dto.reuse_sources and dto.clone_from_task_id is None:
            raise BadRequestException("reuse_sources needs clone_from_task_id")
        task = self._create(dto.to_entity(), dto.clone_from_task_id, dto.reuse_sources)
        self.broker.notify(task.id)
        await self.runner.start(str(task.id))
        return TaskResponseDto.from_entity(task, is_running=True)

    @Transactional
    def _create(self, entity: WritingTaskEntity, clone_from: uuid.UUID | None, reuse_sources: bool) -> WritingTaskEntity:
        if clone_from is not None and self.tasks.get(clone_from) is None:
            raise NotFoundException(f"Task '{clone_from}' not found")
        task = self.tasks.create(entity)
        reused = self._copy_sources(clone_from, task.id) if reuse_sources else 0
        payload = {"reason": "task_created", "mode": str(task.mode)}
        if clone_from is not None:
            payload.update(cloned_from=str(clone_from), reused_sources=reused)
        self.events.add(
            TaskEventEntity(
                task_id=task.id,
                type="status_changed",
                to_status=task.status,
                actor=EventActor.OWNER,
                payload=payload,
            )
        )
        return task

    def _copy_sources(self, from_task: uuid.UUID, to_task: uuid.UUID) -> int:
        """Copy assessed sources (with text) and their claims. Question ids are dropped: the new task re-plans
        its questions, so these claims count as evidence for writing but not as coverage of the new plan."""
        claims_by_source: dict[uuid.UUID, list] = {}
        for claim in self.claims.list_by_task(from_task):
            claims_by_source.setdefault(claim.source_id, []).append(claim)
        copied = 0
        for source in self.sources.list_by_task(from_task, REUSABLE, include_content=True):
            new_source = self.sources.add_if_new(
                source.model_copy(
                    update={"id": None, "task_id": to_task, "round": 0, "created_at": None, "notes": [*source.notes, f"reused from task {from_task}"]}
                )
            )
            if new_source is None:
                continue
            self.claims.replace_for_source(
                new_source.id,
                [
                    claim.model_copy(update={"id": None, "task_id": to_task, "source_id": new_source.id, "question_id": None, "created_at": None})
                    for claim in claims_by_source.get(source.id, [])
                ],
            )
            copied += 1
        return copied


CreateTaskUsecaseDep = Annotated[CreateTaskUsecase, Depends(CreateTaskUsecase)]
