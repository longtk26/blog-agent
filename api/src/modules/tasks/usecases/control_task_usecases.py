import uuid
from typing import Annotated
from fastapi import Depends

from src.libs.decorators.transactional_decorator import Transactional
from src.libs.events import EventBrokerDep
from src.libs.exceptions import BadRequestException, ConflictException, ErrorCode, NotFoundException
from src.modules.agent.ports.output import IWorkflowRunnerDep, ThreadStatus
from src.modules.shared.domain.entities import EventActor, TaskMode, WritingTaskEntity
from src.modules.shared.domain.value_objects import CANCELLABLE_STATUSES, TaskStatus
from src.modules.tasks.ports.output import ITaskEventRepoDep, ITaskRepoDep
from src.modules.tasks.presenter.dtos import PromoteTaskRequestDto, TaskResponseDto
from src.modules.tasks.domain.task_transitions import TaskTransitioner


class _TaskControl():
    def __init__(self, tasks: ITaskRepoDep, events: ITaskEventRepoDep, runner: IWorkflowRunnerDep, broker: EventBrokerDep):
        self.tasks = tasks
        self.events = events
        self.runner = runner
        self.broker = broker
        self.transitioner = TaskTransitioner(tasks, events)

    def _get(self, task_id: uuid.UUID) -> WritingTaskEntity:
        task = self.tasks.get(task_id)
        if task is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        return task

    def _ensure_idle(self, task_id: uuid.UUID) -> None:
        if self.runner.is_running(str(task_id)):
            raise ConflictException("The task is running; wait for it to stop or cancel it", code=ErrorCode.TASK_RUNNING)

    def _response(self, task: WritingTaskEntity) -> TaskResponseDto:
        return TaskResponseDto.from_entity(task, is_running=self.runner.is_running(str(task.id)))


class CancelTaskUsecase(_TaskControl):
    async def execute(self, task_id: uuid.UUID) -> TaskResponseDto:
        task = self._cancel(task_id)
        self.broker.notify(task_id)
        await self.runner.cancel(str(task_id))
        return self._response(task)

    @Transactional
    def _cancel(self, task_id: uuid.UUID) -> WritingTaskEntity:
        task = self._get(task_id)
        if task.status not in CANCELLABLE_STATUSES:
            raise BadRequestException(f"A task in '{task.status}' cannot be cancelled", code=ErrorCode.INVALID_TRANSITION)
        return self.transitioner.transition(task_id, TaskStatus.REJECTED, actor=EventActor.OWNER, reason="cancelled")


class RetryTaskUsecase(_TaskControl):
    async def execute(self, task_id: uuid.UUID) -> TaskResponseDto:
        task = self._get(task_id)
        if task.status != TaskStatus.FAILED or not task.resumable:
            raise BadRequestException("Only failed, resumable tasks can be retried", code=ErrorCode.INVALID_TRANSITION)
        self._ensure_idle(task_id)
        thread = await self.runner.thread_status(str(task_id))
        if thread == ThreadStatus.FINISHED:
            raise ConflictException("The workflow already finished; there is nothing to retry", code=ErrorCode.NOTHING_TO_RESUME)

        task = self._retry(task_id, task.failed_stage or TaskStatus.QUEUED)
        self.broker.notify(task_id)
        if thread == ThreadStatus.NONE:
            await self.runner.start(str(task_id))
        else:
            await self.runner.resume(str(task_id))
        return TaskResponseDto.from_entity(task, is_running=True)

    @Transactional
    def _retry(self, task_id: uuid.UUID, stage: TaskStatus) -> WritingTaskEntity:
        return self.transitioner.transition(task_id, stage, actor=EventActor.OWNER, reason="retry")


class PromoteTaskUsecase(_TaskControl):
    async def execute(self, task_id: uuid.UUID, dto: PromoteTaskRequestDto) -> TaskResponseDto:
        task = self._get(task_id)
        if task.status != TaskStatus.COMPLETED or task.mode != TaskMode.RESEARCH_ONLY:
            raise BadRequestException("Only completed research-only tasks can be promoted", code=ErrorCode.INVALID_TRANSITION)
        self._ensure_idle(task_id)
        if await self.runner.thread_status(str(task_id)) != ThreadStatus.INTERRUPTED:
            raise ConflictException("The research thread is not waiting for promotion", code=ErrorCode.NOTHING_TO_RESUME)

        task = self._promote(task_id, dto)
        self.broker.notify(task_id)
        await self.runner.resume(str(task_id), {"action": "promote", **dto.model_dump(mode="json", exclude_none=True)})
        return TaskResponseDto.from_entity(task, is_running=True)

    @Transactional
    def _promote(self, task_id: uuid.UUID, dto: PromoteTaskRequestDto) -> WritingTaskEntity:
        updates = {"mode": TaskMode.ARTICLE, **dto.model_dump(exclude_none=True)}
        return self.transitioner.transition(
            task_id, TaskStatus.OUTLINING, actor=EventActor.OWNER, reason="promoted_to_article", updates=updates
        )


CancelTaskUsecaseDep = Annotated[CancelTaskUsecase, Depends(CancelTaskUsecase)]
RetryTaskUsecaseDep = Annotated[RetryTaskUsecase, Depends(RetryTaskUsecase)]
PromoteTaskUsecaseDep = Annotated[PromoteTaskUsecase, Depends(PromoteTaskUsecase)]
