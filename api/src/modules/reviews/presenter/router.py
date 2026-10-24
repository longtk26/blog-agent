import uuid

from fastapi import APIRouter, Request, status

from src.configs import config
from src.libs.security import limiter
from src.modules.articles.presenter.dtos import RevisionResponseDto
from src.modules.reviews.presenter.dtos import (
    ApprovalListResponseDto,
    CreateApprovalDto,
    CreateOwnerRevisionDto,
    ReviewRequestDto,
)
from src.modules.reviews.usecases import (
    ApproveRevisionUsecaseDep,
    CreateOwnerRevisionUsecaseDep,
    ListApprovalsUsecaseDep,
    ReviewTaskUsecaseDep,
)
from src.modules.tasks.presenter.dtos import TaskResponseDto


review_router = APIRouter(tags=["reviews"])


@review_router.post("/tasks/{task_id}/revisions", response_model=RevisionResponseDto, status_code=status.HTTP_201_CREATED)
async def create_owner_revision(task_id: uuid.UUID, body: CreateOwnerRevisionDto, usecase: CreateOwnerRevisionUsecaseDep):
    return await usecase.execute(task_id, body)


@review_router.post("/tasks/{task_id}/review", response_model=TaskResponseDto)
@limiter.limit(config.rate_limit_strict)
async def review_task(request: Request, task_id: uuid.UUID, body: ReviewRequestDto, usecase: ReviewTaskUsecaseDep):
    return await usecase.execute(task_id, body)


@review_router.post(
    "/revisions/{revision_id}/approvals", response_model=ApprovalListResponseDto, status_code=status.HTTP_201_CREATED
)
async def approve_revision(revision_id: uuid.UUID, body: CreateApprovalDto, usecase: ApproveRevisionUsecaseDep):
    return await usecase.execute(revision_id, body)


@review_router.get("/tasks/{task_id}/approvals", response_model=ApprovalListResponseDto)
async def list_approvals(task_id: uuid.UUID, usecase: ListApprovalsUsecaseDep):
    return await usecase.execute(task_id)
