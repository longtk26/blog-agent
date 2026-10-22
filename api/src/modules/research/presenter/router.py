import uuid

from fastapi import APIRouter

from src.modules.research.presenter.dtos import ResearchBriefResponseDto, SourceListResponseDto
from src.modules.research.usecases import GetResearchBriefUsecaseDep, ListSourcesUsecaseDep


research_router = APIRouter(prefix="/tasks/{task_id}", tags=["research"])


@research_router.get("/sources", response_model=SourceListResponseDto)
async def list_sources(task_id: uuid.UUID, usecase: ListSourcesUsecaseDep):
    return await usecase.execute(task_id)


@research_router.get("/research-brief", response_model=ResearchBriefResponseDto)
async def get_research_brief(task_id: uuid.UUID, usecase: GetResearchBriefUsecaseDep):
    return await usecase.execute(task_id)
