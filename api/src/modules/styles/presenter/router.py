from fastapi import APIRouter

from src.modules.styles.presenter.dtos import StyleGuideResponseDto, UpdateStyleGuideRequestDto
from src.modules.styles.usecases import GetStyleGuideUsecaseDep, UpdateStyleGuideUsecaseDep


style_router = APIRouter(prefix="/settings", tags=["settings"])


@style_router.get("/style-guide", response_model=StyleGuideResponseDto)
async def get_style_guide(usecase: GetStyleGuideUsecaseDep):
    return await usecase.execute()


@style_router.put("/style-guide", response_model=StyleGuideResponseDto)
async def update_style_guide(body: UpdateStyleGuideRequestDto, usecase: UpdateStyleGuideUsecaseDep):
    return await usecase.execute(body)
