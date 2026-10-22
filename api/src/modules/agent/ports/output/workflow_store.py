import uuid
from abc import ABC, abstractmethod
from typing import Any

from src.modules.shared.domain.entities import (
    ArticleDraftEntity,
    ArticleRevisionEntity,
    EvaluationResultEntity,
    EventActor,
    ResearchBriefEntity,
    ResearchClaimEntity,
    ResearchSourceEntity,
    SourceStatus,
    TaskEventEntity,
    WritingTaskEntity,
)
from src.modules.shared.domain.value_objects import TaskStatus


class IWorkflowStore(ABC):
    """Everything graph nodes and the runner may persist. Each call is its own short transaction;
    nodes never touch sessions or ORM models directly."""

    @abstractmethod
    async def get_task(self, task_id: uuid.UUID) -> WritingTaskEntity:
        pass

    @abstractmethod
    async def list_tasks(self, statuses: list[TaskStatus]) -> list[WritingTaskEntity]:
        pass

    @abstractmethod
    async def transition(
        self,
        task_id: uuid.UUID,
        to_status: TaskStatus,
        *,
        actor: EventActor = EventActor.AGENT,
        reason: str | None = None,
        updates: dict[str, Any] | None = None,
    ) -> WritingTaskEntity:
        pass

    @abstractmethod
    async def fail_task(self, task_id: uuid.UUID, stage: TaskStatus, error: str, resumable: bool = True) -> None:
        pass

    @abstractmethod
    async def update_task(self, task_id: uuid.UUID, **fields: Any) -> WritingTaskEntity:
        pass

    @abstractmethod
    async def record_event(self, task_id: uuid.UUID, type: str, payload: dict | None = None) -> TaskEventEntity:
        pass

    @abstractmethod
    async def add_sources(self, sources: list[ResearchSourceEntity]) -> list[ResearchSourceEntity]:
        """Insert new sources; duplicates by (task_id, canonical_url) are skipped."""
        pass

    @abstractmethod
    async def known_urls(self, task_id: uuid.UUID) -> set[str]:
        pass

    @abstractmethod
    async def list_sources(
        self, task_id: uuid.UUID, statuses: list[SourceStatus] | None = None, include_content: bool = False
    ) -> list[ResearchSourceEntity]:
        pass

    @abstractmethod
    async def update_source(self, source: ResearchSourceEntity) -> ResearchSourceEntity:
        pass

    @abstractmethod
    async def save_assessment(
        self, source: ResearchSourceEntity, claims: list[ResearchClaimEntity]
    ) -> list[ResearchClaimEntity]:
        pass

    @abstractmethod
    async def list_claims(self, task_id: uuid.UUID) -> list[ResearchClaimEntity]:
        pass

    @abstractmethod
    async def source_counts(self, task_id: uuid.UUID) -> dict[str, int]:
        pass

    @abstractmethod
    async def save_brief(self, brief: ResearchBriefEntity) -> ResearchBriefEntity:
        pass

    @abstractmethod
    async def get_brief(self, task_id: uuid.UUID) -> ResearchBriefEntity | None:
        pass

    @abstractmethod
    async def get_draft(self, task_id: uuid.UUID) -> ArticleDraftEntity | None:
        pass

    @abstractmethod
    async def save_draft(self, draft: ArticleDraftEntity) -> ArticleDraftEntity:
        pass

    @abstractmethod
    async def slug_taken(self, slug: str, task_id: uuid.UUID) -> bool:
        """True if another task already uses this slug for a revision."""
        pass

    @abstractmethod
    async def latest_revision(self, task_id: uuid.UUID) -> ArticleRevisionEntity | None:
        pass

    @abstractmethod
    async def create_revision(
        self, revision: ArticleRevisionEntity, evaluations: list[EvaluationResultEntity]
    ) -> ArticleRevisionEntity:
        """Insert an immutable revision and its evaluation results in one transaction."""
        pass

    @abstractmethod
    async def style_guide(self) -> tuple[str, str]:
        """(version, content) of the active style guide."""
        pass
