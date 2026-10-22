import uuid
from typing import Annotated
from fastapi import Depends

from src.libs.exceptions import NotFoundException
from src.modules.agent.ports.output import ITracingDep, IWorkflowRunnerDep
from src.modules.tasks.ports.output import ITaskRepoDep
from src.modules.tasks.presenter.dtos import TaskResponseDto


class GetTaskUsecase():
    def __init__(self, tasks: ITaskRepoDep, runner: IWorkflowRunnerDep, tracing: ITracingDep):
        self.tasks = tasks
        self.runner = runner
        self.tracing = tracing

    async def execute(self, task_id: uuid.UUID) -> TaskResponseDto:
        task = self.tasks.get(task_id)
        if task is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        trace_url = await self.tracing.run_url(task.last_run_id) if task.last_run_id else None
        return TaskResponseDto.from_entity(task, is_running=self.runner.is_running(str(task_id)), trace_url=trace_url)


GetTaskUsecaseDep = Annotated[GetTaskUsecase, Depends(GetTaskUsecase)]
