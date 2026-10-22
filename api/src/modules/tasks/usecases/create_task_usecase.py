from typing import Annotated
from fastapi import Depends

from src.libs.decorators.transactional_decorator import Transactional
from src.libs.events import EventBrokerDep
from src.modules.agent.ports.output import IWorkflowRunnerDep
from src.modules.shared.domain.entities import EventActor, TaskEventEntity, WritingTaskEntity
from src.modules.tasks.ports.output import ITaskEventRepoDep, ITaskRepoDep
from src.modules.tasks.presenter.dtos import CreateTaskRequestDto, TaskResponseDto


class CreateTaskUsecase():
    def __init__(self, tasks: ITaskRepoDep, events: ITaskEventRepoDep, runner: IWorkflowRunnerDep, broker: EventBrokerDep):
        self.tasks = tasks
        self.events = events
        self.runner = runner
        self.broker = broker

    async def execute(self, dto: CreateTaskRequestDto) -> TaskResponseDto:
        task = self._create(dto.to_entity())
        self.broker.notify(task.id)
        await self.runner.start(str(task.id))
        return TaskResponseDto.from_entity(task, is_running=True)

    @Transactional
    def _create(self, entity: WritingTaskEntity) -> WritingTaskEntity:
        task = self.tasks.create(entity)
        self.events.add(
            TaskEventEntity(
                task_id=task.id,
                type="status_changed",
                to_status=task.status,
                actor=EventActor.OWNER,
                payload={"reason": "task_created", "mode": str(task.mode)},
            )
        )
        return task


CreateTaskUsecaseDep = Annotated[CreateTaskUsecase, Depends(CreateTaskUsecase)]
