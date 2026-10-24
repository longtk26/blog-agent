import uuid

from fastapi import APIRouter, status

from src.libs.exceptions import NotFoundException
from src.modules.articles.ports.output import IRevisionRepoDep
from src.modules.publishing.domain import render_for_devto
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


@publishing_router.get(
    "/revisions/{revision_id}/render/devto",
    status_code=status.HTTP_200_OK,
)
async def preview_devto_render(
    revision_id: uuid.UUID,
    revisions: IRevisionRepoDep,
):
    rev = revisions.get(revision_id)
    if rev is None:
        raise NotFoundException(f"Revision '{revision_id}' not found")
    res = await render_for_devto(rev)
    return {
        "title": res.title,
        "body_markdown": res.body_markdown,
        "rendered_content_hash": res.rendered_content_hash,
        "tags": res.tags,
        "canonical_url": res.canonical_url,
        "main_image": res.main_image,
        "description": res.description,
    }



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
