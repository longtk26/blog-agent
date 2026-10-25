import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.configs import config
from src.modules.shared.domain.entities import (
    IncludeDiagram,
    PublicationTarget,
    SeriesInfo,
    TaskBudgets,
    TaskDepth,
    TaskEventEntity,
    TaskFormat,
    TaskMode,
    TaskProgress,
    WritingTaskEntity,
)
from src.modules.shared.domain.value_objects import TaskStatus


class SeriesDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    part: int | None = Field(default=None, ge=1, le=100)
    previous_post_id: str | None = Field(default=None, max_length=120)


class TaskBudgetsDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_queries: int | None = Field(default=None, ge=1, le=config.research_max_queries)
    max_sources: int | None = Field(default=None, ge=1, le=config.research_max_sources)
    max_research_rounds: int | None = Field(default=None, ge=1, le=config.research_max_rounds)
    results_per_query: int | None = Field(default=None, ge=1, le=10)
    max_cost_usd: float | None = Field(default=None, ge=0.01, le=100.0)


class CreateTaskRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=5, max_length=500)
    mode: TaskMode = TaskMode.ARTICLE
    audience: str | None = Field(default=None, max_length=300)
    depth: TaskDepth = TaskDepth.INTERMEDIATE
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    format: TaskFormat = TaskFormat.CONCEPT
    series: SeriesDto | None = None
    requirements: str | None = Field(default=None, max_length=4000)
    include_diagram: IncludeDiagram = IncludeDiagram.AUTO
    diagram_format: str = "auto"
    review_outline: bool = False
    use_style_examples: bool = True
    publication_targets: list[PublicationTarget] = Field(default_factory=list)
    budgets: TaskBudgetsDto | None = None
    # Clone (E4-S8): the UI prefills the form from this task; reuse_sources copies its assessed sources and claims.
    clone_from_task_id: uuid.UUID | None = None
    reuse_sources: bool = False

    @field_validator("topic", "audience", "requirements")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("publication_targets")
    @classmethod
    def unique_targets(cls, value: list[PublicationTarget]) -> list[PublicationTarget]:
        return list(dict.fromkeys(value))

    def to_entity(self) -> WritingTaskEntity:
        overrides = self.budgets.model_dump(exclude_none=True) if self.budgets else {}
        return WritingTaskEntity(
            topic=self.topic,
            mode=self.mode,
            audience=self.audience,
            depth=self.depth,
            language=self.language,
            format=self.format,
            series=SeriesInfo(**self.series.model_dump()) if self.series else None,
            requirements=self.requirements,
            include_diagram=self.include_diagram,
            diagram_format=self.diagram_format,
            review_outline=self.review_outline,
            use_style_examples=self.use_style_examples,
            publication_targets=self.publication_targets,
            budgets=TaskBudgets(**overrides),
            status=TaskStatus.QUEUED,
        )


class PromoteTaskRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    angle: str | None = Field(default=None, max_length=300)
    audience: str | None = Field(default=None, max_length=300)
    depth: TaskDepth | None = None
    format: TaskFormat | None = None
    requirements: str | None = Field(default=None, max_length=4000)


class OutlineSectionEditDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^s\d{1,2}$")
    heading: str = Field(min_length=2, max_length=200)
    heading_style: Literal["numbered", "step", "plain"] = "numbered"
    goal: str = Field(default="", max_length=1000)
    key_points: list[str] = Field(default_factory=list, max_length=10)
    needs: list[str] = Field(default_factory=list, max_length=7)
    est_words: int = Field(default=300, ge=80, le=1500)
    claim_ids: list[str] = Field(default_factory=list, max_length=80)


class OutlineEditDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    angle: str | None = Field(default=None, max_length=500)
    intro_goal: str | None = Field(default=None, max_length=1000)
    sections: list[OutlineSectionEditDto] | None = Field(default=None, min_length=1, max_length=12)


class ApproveOutlineRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outline: OutlineEditDto | None = None


class TaskResponseDto(BaseModel):
    id: uuid.UUID
    topic: str
    mode: TaskMode
    audience: str | None
    depth: TaskDepth
    language: str
    format: TaskFormat
    series: SeriesInfo | None
    requirements: str | None
    angle: str | None
    include_diagram: IncludeDiagram
    diagram_format: str = "auto"
    review_outline: bool
    use_style_examples: bool = True
    publication_targets: list[PublicationTarget]
    budgets: TaskBudgets
    status: TaskStatus
    failed_stage: TaskStatus | None
    last_error: str | None
    resumable: bool
    research_plan: dict | None
    outline: dict | None
    open_questions: list[str]
    progress: TaskProgress
    is_running: bool
    pending_interrupt: dict | None = None
    trace_url: str | None
    total_cost_usd: float = 0.0
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(
        cls,
        task: WritingTaskEntity,
        is_running: bool,
        trace_url: str | None = None,
        pending_interrupt: dict | None = None,
        total_cost_usd: float | None = None,
    ) -> "TaskResponseDto":
        dump = task.model_dump(exclude={"last_run_id"})
        if total_cost_usd is not None:
            dump["total_cost_usd"] = total_cost_usd
        return cls(
            **dump,
            is_running=is_running,
            trace_url=trace_url,
            pending_interrupt=pending_interrupt,
        )


class TaskSummaryDto(BaseModel):
    id: uuid.UUID
    topic: str
    mode: TaskMode
    format: TaskFormat
    status: TaskStatus
    progress: TaskProgress
    last_error: str | None
    is_running: bool
    total_cost_usd: float = 0.0
    created_at: datetime
    updated_at: datetime


class TaskListResponseDto(BaseModel):
    items: list[TaskSummaryDto]
    total: int
    limit: int
    offset: int


class StageUsageDto(BaseModel):
    stage: str
    calls: int
    models: list[str]
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    latency_ms: int
    cost_usd: float


class TaskUsageResponseDto(BaseModel):
    task_id: uuid.UUID
    stages: list[StageUsageDto]
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    total_tokens: int
    total_latency_ms: int
    total_cost_usd: float
    is_estimate: bool = True


class TaskEventDto(BaseModel):
    id: int
    type: str
    from_status: str | None
    to_status: str | None
    actor: str
    payload: dict
    created_at: datetime

    @classmethod
    def from_entity(cls, event: TaskEventEntity) -> "TaskEventDto":
        return cls(**event.model_dump(exclude={"task_id"}))
