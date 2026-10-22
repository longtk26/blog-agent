import uuid

from fastapi import APIRouter

from src.modules.articles.presenter.dtos import RevisionListResponseDto, RevisionResponseDto
from src.modules.articles.usecases import GetRevisionUsecaseDep, ListRevisionsUsecaseDep


article_router = APIRouter(tags=["articles"])


@article_router.get("/tasks/{task_id}/revisions", response_model=RevisionListResponseDto)
async def list_revisions(task_id: uuid.UUID, usecase: ListRevisionsUsecaseDep):
    return await usecase.execute(task_id)


@article_router.get("/revisions/{revision_id}", response_model=RevisionResponseDto)
async def get_revision(revision_id: uuid.UUID, usecase: GetRevisionUsecaseDep):
    return await usecase.execute(revision_id)
