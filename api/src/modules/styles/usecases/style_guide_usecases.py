from typing import Annotated
from fastapi import Depends

from src.libs.decorators.transactional_decorator import Transactional
from src.modules.shared.domain.entities import StyleGuideEntity
from src.modules.styles.domain.active_style import resolve_active_style
from src.modules.styles.ports.output import IStyleGuideRepoDep
from src.modules.styles.presenter.dtos import StyleGuideResponseDto, UpdateStyleGuideRequestDto


def active_style_guide(latest: StyleGuideEntity | None) -> StyleGuideResponseDto:
    active = resolve_active_style(latest)
    return StyleGuideResponseDto(version=active.version, content=active.content, source=active.source, updated_at=active.updated_at)


class GetStyleGuideUsecase():
    def __init__(self, guides: IStyleGuideRepoDep):
        self.guides = guides

    async def execute(self) -> StyleGuideResponseDto:
        return active_style_guide(self.guides.latest())


class UpdateStyleGuideUsecase():
    def __init__(self, guides: IStyleGuideRepoDep):
        self.guides = guides

    @Transactional
    async def execute(self, dto: UpdateStyleGuideRequestDto) -> StyleGuideResponseDto:
        version = f"owner-{self.guides.count() + 1}"
        guide = self.guides.create(StyleGuideEntity(version=version, content=dto.content.strip(), created_by="owner"))
        return active_style_guide(guide)


GetStyleGuideUsecaseDep = Annotated[GetStyleGuideUsecase, Depends(GetStyleGuideUsecase)]
UpdateStyleGuideUsecaseDep = Annotated[UpdateStyleGuideUsecase, Depends(UpdateStyleGuideUsecase)]
