import uuid
from typing import Annotated
from fastapi import Depends

from src.libs.exceptions import NotFoundException
from src.modules.research.ports.output import IBriefRepoDep
from src.modules.research.presenter.dtos import ResearchBriefResponseDto


class GetResearchBriefUsecase():
    def __init__(self, briefs: IBriefRepoDep):
        self.briefs = briefs

    async def execute(self, task_id: uuid.UUID) -> ResearchBriefResponseDto:
        brief = self.briefs.get_by_task(task_id)
        if brief is None:
            raise NotFoundException("No research brief for this task yet")
        return ResearchBriefResponseDto(**brief.model_dump())


GetResearchBriefUsecaseDep = Annotated[GetResearchBriefUsecase, Depends(GetResearchBriefUsecase)]
