import uuid
from typing import Any

from src.libs.exceptions import NotFoundException
from src.modules.shared.domain.entities import EventActor, TaskEventEntity, WritingTaskEntity
from src.modules.shared.domain.value_objects import TaskStatus, ensure_transition
from src.modules.tasks.ports.output import ITaskEventRepository, ITaskRepository


class TaskTransitioner:
    """The only code path that changes `writing_tasks.status`.

    Every change is validated against the state machine and recorded as a `status_changed`
    event in the caller's transaction (request `@Transactional` or a workflow session).
    """

    def __init__(self, tasks: ITaskRepository, events: ITaskEventRepository):
        self.tasks = tasks
        self.events = events

    def transition(
        self,
        task_id: uuid.UUID,
        to_status: TaskStatus,
        *,
        actor: EventActor,
        reason: str | None = None,
        failed_stage: TaskStatus | None = None,
        error: str | None = None,
        resumable: bool = False,
        updates: dict[str, Any] | None = None,
    ) -> WritingTaskEntity:
        task = self.tasks.get(task_id, for_update=True)
        if task is None:
            raise NotFoundException(f"Task '{task_id}' not found")

        from_status = task.status
        ensure_transition(from_status, to_status, task.failed_stage)

        task.status = to_status
        if to_status == TaskStatus.FAILED:
            task.failed_stage = failed_stage or from_status
            task.last_error = error
            task.resumable = resumable
        elif from_status == TaskStatus.FAILED:
            task.failed_stage = None
            task.last_error = None
            task.resumable = False
        for field, value in (updates or {}).items():
            setattr(task, field, value)

        task = self.tasks.update(task)
        payload: dict[str, Any] = {}
        if reason:
            payload["reason"] = reason
        if error:
            payload["error"] = error
        self.events.add(
            TaskEventEntity(
                task_id=task_id,
                type="status_changed",
                from_status=from_status,
                to_status=to_status,
                actor=actor,
                payload=payload,
            )
        )
        return task

    def record(
        self, task_id: uuid.UUID, type: str, payload: dict | None = None, actor: EventActor = EventActor.AGENT
    ) -> TaskEventEntity:
        return self.events.add(TaskEventEntity(task_id=task_id, type=type, actor=actor, payload=payload or {}))
