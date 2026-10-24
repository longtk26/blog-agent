import uuid

from fastapi import APIRouter, status

from src.modules.publishing.presenter.dtos import (
    PublicationListResponseDto,
    PublishRequestDto,
    UnpublishRequestDto,
)
from src.modules.publishing.usecases import (
    ListPublicationsUsecaseDep,
    PublishRevisionUsecaseDep,
    RetryPublicationUsecaseDep,
    UnpublishUsecaseDep,
)
from src.modules.shared.domain.entities import PublicationTarget

publishing_router = APIRouter(tags=["publishing"])


@publishing_router.post(
    "/revisions/{revision_id}/publish",
    response_model=PublicationListResponseDto,
    status_code=status.HTTP_200_OK,
)
async def publish_revision(
    revision_id: uuid.UUID,
    body: PublishRequestDto,
    usecase: PublishRevisionUsecaseDep,
):
    return await usecase.execute(revision_id, body)


@publishing_router.get(
    "/tasks/{task_id}/publications",
    response_model=PublicationListResponseDto,
    status_code=status.HTTP_200_OK,
)
async def list_publications(
    task_id: uuid.UUID,
    usecase: ListPublicationsUsecaseDep,
):
    return await usecase.execute(task_id)


@publishing_router.post(
    "/tasks/{task_id}/publications/{destination}/retry",
    response_model=PublicationListResponseDto,
    status_code=status.HTTP_200_OK,
)
async def retry_publication(
    task_id: uuid.UUID,
    destination: PublicationTarget,
    usecase: RetryPublicationUsecaseDep,
):
    return await usecase.execute(task_id, destination)


@publishing_router.post(
    "/tasks/{task_id}/unpublish",
    response_model=PublicationListResponseDto,
    status_code=status.HTTP_200_OK,
)
async def unpublish_task(
    task_id: uuid.UUID,
    body: UnpublishRequestDto,
    usecase: UnpublishUsecaseDep,
):
    return await usecase.execute(task_id, body)
