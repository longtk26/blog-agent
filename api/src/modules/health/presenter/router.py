from fastapi import APIRouter, Request

from src.configs import config
from src.libs.exceptions import NotFoundException
from src.libs.security import limiter
from src.modules.health.usecases import GraphPingUsecaseDep, HealthCheckUsecaseDep, PingLlmUsecaseDep
from src.modules.health.presenter.dtos import (
    GraphPingRequestDto,
    GraphPingResponseDto,
    HealthCheckResponseDto,
    LlmPingResponseDto,
)


health_router = APIRouter(tags=["health"])


def _require_debug() -> None:
    if not config.debug:
        raise NotFoundException("Not found")


@health_router.get("/health", response_model=HealthCheckResponseDto)
async def health_check(usecase: HealthCheckUsecaseDep):
    return await usecase.execute()


@health_router.get("/health/llm", response_model=LlmPingResponseDto)
@limiter.limit(config.rate_limit_strict)
async def ping_llm(request: Request, usecase: PingLlmUsecaseDep):
    _require_debug()
    return await usecase.execute()


@health_router.post("/health/graph", response_model=GraphPingResponseDto)
@limiter.limit(config.rate_limit_strict)
async def ping_graph(request: Request, body: GraphPingRequestDto, usecase: GraphPingUsecaseDep):
    _require_debug()
    return await usecase.execute(body)
