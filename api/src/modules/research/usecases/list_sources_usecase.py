import uuid
from collections import defaultdict
from typing import Annotated
from fastapi import Depends

from src.libs.exceptions import NotFoundException
from src.modules.research.ports.output import IClaimRepoDep, ISourceRepoDep
from src.modules.research.presenter.dtos import SourceDto, SourceListResponseDto
from src.modules.tasks.ports.output import ITaskRepoDep


class ListSourcesUsecase():
    def __init__(self, tasks: ITaskRepoDep, sources: ISourceRepoDep, claims: IClaimRepoDep):
        self.tasks = tasks
        self.sources = sources
        self.claims = claims

    async def execute(self, task_id: uuid.UUID) -> SourceListResponseDto:
        if self.tasks.get(task_id) is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        claims_by_source = defaultdict(list)
        for claim in self.claims.list_by_task(task_id):
            claims_by_source[claim.source_id].append(claim)
        sources = self.sources.list_by_task(task_id)
        # Best evidence first: quality desc, then failed/pending last.
        sources.sort(key=lambda s: (s.quality_score is None, -(s.quality_score or 0)))
        items = [SourceDto.from_entity(s, claims_by_source.get(s.id, [])) for s in sources]
        return SourceListResponseDto(items=items, total=len(items))


ListSourcesUsecaseDep = Annotated[ListSourcesUsecase, Depends(ListSourcesUsecase)]
