import uuid
from typing import Any

from src.configs.logger import get_logger
from src.libs.database import arun_in_session
from src.libs.events import TaskEventBroker
from src.libs.exceptions import NotFoundException
from src.modules.agent.ports.output.workflow_store import IWorkflowStore
from src.modules.research.infrastructure.persistence import BriefRepository, ClaimRepository, SourceRepository
from src.modules.shared.domain.entities import (
    EventActor,
    ResearchBriefEntity,
    ResearchClaimEntity,
    ResearchSourceEntity,
    SourceStatus,
    TaskEventEntity,
    WritingTaskEntity,
)
from src.modules.shared.domain.value_objects import TaskStatus, can_transition
from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository
from src.modules.tasks.domain.task_transitions import TaskTransitioner

logger = get_logger(__name__)


def _transitioner(session) -> TaskTransitioner:
    return TaskTransitioner(TaskRepository(session), TaskEventRepository(session))


class WorkflowStore(IWorkflowStore):
    def __init__(self, broker: TaskEventBroker):
        self.broker = broker

    async def get_task(self, task_id: uuid.UUID) -> WritingTaskEntity:
        task = await arun_in_session(lambda s: TaskRepository(s).get(task_id))
        if task is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        return task

    async def list_tasks(self, statuses: list[TaskStatus]) -> list[WritingTaskEntity]:
        return await arun_in_session(lambda s: TaskRepository(s).list_by_statuses(statuses))

    async def transition(
        self,
        task_id: uuid.UUID,
        to_status: TaskStatus,
        *,
        actor: EventActor = EventActor.AGENT,
        reason: str | None = None,
        updates: dict[str, Any] | None = None,
    ) -> WritingTaskEntity:
        task = await arun_in_session(
            lambda s: _transitioner(s).transition(task_id, to_status, actor=actor, reason=reason, updates=updates)
        )
        self.broker.notify(task_id)
        return task

    async def fail_task(self, task_id: uuid.UUID, stage: TaskStatus, error: str, resumable: bool = True) -> None:
        def run(session):
            transitioner = _transitioner(session)
            task = transitioner.tasks.get(task_id, for_update=True)
            if task is None or not can_transition(task.status, TaskStatus.FAILED):
                # e.g. already rejected/cancelled: keep that status, only log the error.
                transitioner.record(task_id, "error", {"stage": str(stage), "message": error})
                return
            transitioner.transition(
                task_id,
                TaskStatus.FAILED,
                actor=EventActor.SYSTEM,
                failed_stage=stage,
                error=error,
                resumable=resumable,
            )

        await arun_in_session(run)
        self.broker.notify(task_id)

    async def update_task(self, task_id: uuid.UUID, **fields: Any) -> WritingTaskEntity:
        def run(session):
            repo = TaskRepository(session)
            task = repo.get(task_id, for_update=True)
            for field, value in fields.items():
                setattr(task, field, value)
            return repo.update(task)

        return await arun_in_session(run)

    async def record_event(self, task_id: uuid.UUID, type: str, payload: dict | None = None) -> TaskEventEntity:
        event = await arun_in_session(
            lambda s: TaskEventRepository(s).add(TaskEventEntity(task_id=task_id, type=type, actor=EventActor.AGENT, payload=payload or {}))
        )
        self.broker.notify(task_id)
        return event

    async def add_sources(self, sources: list[ResearchSourceEntity]) -> list[ResearchSourceEntity]:
        def run(session):
            repo = SourceRepository(session)
            return [inserted for source in sources if (inserted := repo.add_if_new(source)) is not None]

        return await arun_in_session(run)

    async def known_urls(self, task_id: uuid.UUID) -> set[str]:
        return await arun_in_session(lambda s: SourceRepository(s).canonical_urls(task_id))

    async def list_sources(
        self, task_id: uuid.UUID, statuses: list[SourceStatus] | None = None, include_content: bool = False
    ) -> list[ResearchSourceEntity]:
        return await arun_in_session(lambda s: SourceRepository(s).list_by_task(task_id, statuses, include_content))

    async def update_source(self, source: ResearchSourceEntity) -> ResearchSourceEntity:
        return await arun_in_session(lambda s: SourceRepository(s).update(source))

    async def save_assessment(
        self, source: ResearchSourceEntity, claims: list[ResearchClaimEntity]
    ) -> list[ResearchClaimEntity]:
        def run(session):
            SourceRepository(session).update(source)
            return ClaimRepository(session).replace_for_source(source.id, claims)

        return await arun_in_session(run)

    async def list_claims(self, task_id: uuid.UUID) -> list[ResearchClaimEntity]:
        return await arun_in_session(lambda s: ClaimRepository(s).list_by_task(task_id))

    async def source_counts(self, task_id: uuid.UUID) -> dict[str, int]:
        return await arun_in_session(lambda s: SourceRepository(s).count_by_status(task_id))

    async def save_brief(self, brief: ResearchBriefEntity) -> ResearchBriefEntity:
        return await arun_in_session(lambda s: BriefRepository(s).upsert(brief))
