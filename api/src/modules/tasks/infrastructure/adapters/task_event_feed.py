import uuid
from typing import Annotated

from fastapi import Depends

from src.libs.database import arun_in_session
from src.modules.shared.domain.entities import TaskEventEntity
from src.modules.shared.domain.value_objects import TaskStatus
from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository
from src.modules.tasks.ports.output.task_event_feed import ITaskEventFeed


class TaskEventFeed(ITaskEventFeed):
    async def events_after(self, task_id: uuid.UUID, after_id: int) -> list[TaskEventEntity]:
        return await arun_in_session(lambda s: TaskEventRepository(s).list_after(task_id, after_id))

    async def status(self, task_id: uuid.UUID) -> TaskStatus | None:
        task = await arun_in_session(lambda s: TaskRepository(s).get(task_id))
        return task.status if task else None


ITaskEventFeedDep = Annotated[ITaskEventFeed, Depends(TaskEventFeed)]
