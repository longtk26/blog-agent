from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ComponentStatusDto(BaseModel):
    ok: bool


class LlmStatusDto(BaseModel):
    configured: bool
    default_provider: str | None
    roles: dict[str, str | None]


class TracingStatusDto(BaseModel):
    enabled: bool
    project: str | None


class SearchStatusDto(BaseModel):
    provider: str


class HealthCheckResponseDto(BaseModel):
    status: Literal["healthy", "degraded"]
    app: str
    env: str
    database: ComponentStatusDto
    checkpointer: ComponentStatusDto
    llm: LlmStatusDto
    search: SearchStatusDto
    tracing: TracingStatusDto


class LlmRolePingDto(BaseModel):
    model: str | None
    ok: bool
    latency_ms: int | None = None
    error: str | None = None


class LlmPingResponseDto(BaseModel):
    roles: dict[str, LlmRolePingDto]


class GraphPingRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str = Field(default="health-ping", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    use_llm: bool = False


class GraphPingResponseDto(BaseModel):
    thread_id: str
    count: int
    reply: str
    run_id: str
    trace_url: str | None
