import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from src.configs import config
from src.libs.security import limiter
from src.modules.shared.domain.entities import TaskMode
from src.modules.shared.domain.value_objects import TaskStatus
from src.modules.tasks.presenter.dtos import (
    ApproveOutlineRequestDto,
    CreateTaskRequestDto,
    PromoteTaskRequestDto,
    TaskListResponseDto,
    TaskResponseDto,
)
from src.modules.tasks.usecases import (
    ApproveOutlineUsecaseDep,
    CancelTaskUsecaseDep,
    CreateTaskUsecaseDep,
    GetTaskUsecaseDep,
    ListTasksUsecaseDep,
    PromoteTaskUsecaseDep,
    RetryTaskUsecaseDep,
    StreamTaskEventsUsecaseDep,
)


task_router = APIRouter(prefix="/tasks", tags=["tasks"])


@task_router.post("", response_model=TaskResponseDto, status_code=status.HTTP_201_CREATED)
@limiter.limit(config.rate_limit_strict)
async def create_task(request: Request, body: CreateTaskRequestDto, usecase: CreateTaskUsecaseDep):
    return await usecase.execute(body)


@task_router.get("", response_model=TaskListResponseDto)
async def list_tasks(
    usecase: ListTasksUsecaseDep,
    status: Annotated[list[TaskStatus] | None, Query()] = None,
    mode: TaskMode | None = None,
    archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await usecase.execute(status, mode, limit, offset, archived)


@task_router.get("/{task_id}", response_model=TaskResponseDto)
async def get_task(task_id: uuid.UUID, usecase: GetTaskUsecaseDep):
    return await usecase.execute(task_id)


@task_router.post("/{task_id}/cancel", response_model=TaskResponseDto)
async def cancel_task(task_id: uuid.UUID, usecase: CancelTaskUsecaseDep):
    return await usecase.execute(task_id)


@task_router.post("/{task_id}/retry", response_model=TaskResponseDto)
@limiter.limit(config.rate_limit_strict)
async def retry_task(request: Request, task_id: uuid.UUID, usecase: RetryTaskUsecaseDep):
    return await usecase.execute(task_id)


@task_router.post("/{task_id}/promote", response_model=TaskResponseDto)
@limiter.limit(config.rate_limit_strict)
async def promote_task(request: Request, task_id: uuid.UUID, body: PromoteTaskRequestDto, usecase: PromoteTaskUsecaseDep):
    return await usecase.execute(task_id, body)


@task_router.post("/{task_id}/outline/approve", response_model=TaskResponseDto)
async def approve_outline(task_id: uuid.UUID, body: ApproveOutlineRequestDto, usecase: ApproveOutlineUsecaseDep):
    return await usecase.execute(task_id, body)


@task_router.get("/{task_id}/events")
async def stream_task_events(
    request: Request,
    task_id: uuid.UUID,
    usecase: StreamTaskEventsUsecaseDep,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[int | None, Header()] = None,
):
    stream = await usecase.open(task_id, max(after, last_event_id or 0), request.is_disconnected)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@task_router.get("/{task_id}/usage")
async def get_task_usage(task_id: uuid.UUID):
    from src.libs.database import arun_in_session
    from src.modules.agent.infrastructure.persistence.run_usage_repository import RunUsageRepository

    return await arun_in_session(lambda s: RunUsageRepository(s).usage_breakdown(task_id))

