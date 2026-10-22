import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.modules.shared.domain.value_objects import TaskStatus


class TaskMode(StrEnum):
    RESEARCH_ONLY = "research_only"
    ARTICLE = "article"


class TaskDepth(StrEnum):
    INTRO = "intro"
    INTERMEDIATE = "intermediate"
    DEEP_DIVE = "deep_dive"


class TaskFormat(StrEnum):
    CONCEPT = "concept"
    TUTORIAL = "tutorial"
    COMPARISON = "comparison"
    SERIES_PART = "series_part"


class IncludeDiagram(StrEnum):
    AUTO = "auto"
    YES = "yes"
    NO = "no"


class PublicationTarget(StrEnum):
    SANITY = "sanity"
    DEVTO = "devto"


class SeriesInfo(BaseModel):
    name: str
    part: int | None = None
    previous_post_id: str | None = None


class TaskBudgets(BaseModel):
    max_queries: int = 8
    max_sources: int = 15
    max_research_rounds: int = 2
    results_per_query: int = 5


class TaskProgress(BaseModel):
    round: int = 0
    queries_used: int = 0
    sources_found: int = 0
    sources_extracted: int = 0
    sources_assessed: int = 0
    claims: int = 0


class WritingTaskEntity(BaseModel):
    id: uuid.UUID | None = None
    topic: str
    mode: TaskMode = TaskMode.ARTICLE
    audience: str | None = None
    depth: TaskDepth = TaskDepth.INTERMEDIATE
    language: str = "en"
    format: TaskFormat = TaskFormat.CONCEPT
    series: SeriesInfo | None = None
    requirements: str | None = None
    angle: str | None = None
    include_diagram: IncludeDiagram = IncludeDiagram.AUTO
    publication_targets: list[PublicationTarget] = Field(default_factory=list)
    budgets: TaskBudgets = Field(default_factory=TaskBudgets)

    status: TaskStatus = TaskStatus.QUEUED
    failed_stage: TaskStatus | None = None
    last_error: str | None = None
    resumable: bool = False
    research_plan: dict | None = None
    open_questions: list[str] = Field(default_factory=list)
    progress: TaskProgress = Field(default_factory=TaskProgress)
    last_run_id: uuid.UUID | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None
