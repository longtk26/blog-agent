from typing import Annotated
from fastapi import Depends

from src.modules.agent.ports.output import IWorkflowRunnerDep
from src.modules.shared.domain.value_objects import TaskStatus
from src.modules.tasks.ports.output import ITaskRepoDep
from src.modules.tasks.presenter.dtos import TaskListResponseDto, TaskSummaryDto


class ListTasksUsecase():
    def __init__(self, tasks: ITaskRepoDep, runner: IWorkflowRunnerDep):
        self.tasks = tasks
        self.runner = runner

    async def execute(
        self,
        statuses: list[TaskStatus] | None,
        mode: str | None,
        limit: int,
        offset: int,
        archived: bool = False,
    ) -> TaskListResponseDto:
        if not statuses and not archived:
            statuses = [s for s in TaskStatus if s != TaskStatus.REJECTED]
        items, total = self.tasks.list_page(statuses=statuses, mode=mode, limit=limit, offset=offset)
        return TaskListResponseDto(
            items=[
                TaskSummaryDto(**task.model_dump(), is_running=self.runner.is_running(str(task.id)))
                for task in items
            ],
            total=total,
            limit=limit,
            offset=offset,
        )


ListTasksUsecaseDep = Annotated[ListTasksUsecase, Depends(ListTasksUsecase)]
