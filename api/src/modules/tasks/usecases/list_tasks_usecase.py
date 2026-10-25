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
        from src.modules.agent.infrastructure.persistence.run_usage_repository import RunUsageRepository
        costs = RunUsageRepository(self.tasks.session).total_cost_by_tasks([t.id for t in items])
        items_dto = []
        for task in items:
            data = task.model_dump()
            data["total_cost_usd"] = costs.get(task.id, data.get("total_cost_usd", 0.0))
            items_dto.append(
                TaskSummaryDto(
                    **data,
                    is_running=self.runner.is_running(str(task.id)),
                )
            )
        return TaskListResponseDto(
            items=items_dto,
            total=total,
            limit=limit,
            offset=offset,
        )


ListTasksUsecaseDep = Annotated[ListTasksUsecase, Depends(ListTasksUsecase)]
