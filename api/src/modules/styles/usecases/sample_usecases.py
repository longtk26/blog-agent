from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
import uuid

from fastapi import Depends
from sqlalchemy import func
from sqlmodel import select

from src.libs.database.session import SessionDep
from src.libs.exceptions import NotFoundException
from src.modules.shared.domain.entities import WritingSampleEntity
from src.modules.shared.infrastructure.models import SampleChunkModel, WritingSampleModel
from src.modules.styles.ports.output import (
    IVectorStore,
    IVectorStoreDep,
    IWritingSampleRepoDep,
    IWritingSampleRepository,
)


@dataclass
class WritingSampleDto:
    id: uuid.UUID
    origin: str
    remote_id: str
    title: str
    tags: list[str]
    published_at: datetime | None
    approved_as_style_example: bool
    content_hash: str
    chunk_count: int
    created_at: datetime | None
    updated_at: datetime | None


class ListSamplesUsecase:
    def __init__(self, session: SessionDep, sample_repo: IWritingSampleRepoDep):
        self.session = session
        self.sample_repo: IWritingSampleRepository = sample_repo

    async def execute(self, approved_only: bool = False) -> list[WritingSampleDto]:
        samples = self.sample_repo.list_all(approved_only=approved_only)
        if not samples:
            return []

        # Count chunks per sample
        stmt = (
            select(SampleChunkModel.sample_id, func.count(SampleChunkModel.id))
            .where(SampleChunkModel.sample_id.is_not(None))
            .group_by(SampleChunkModel.sample_id)
        )
        counts = dict(self.session.exec(stmt).all())

        return [
            WritingSampleDto(
                id=s.id,
                origin=s.origin,
                remote_id=s.remote_id,
                title=s.title,
                tags=s.tags,
                published_at=s.published_at,
                approved_as_style_example=s.approved_as_style_example,
                content_hash=s.content_hash,
                chunk_count=counts.get(s.id, 0),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in samples
        ]


class ToggleSampleApprovalUsecase:
    def __init__(self, sample_repo: IWritingSampleRepoDep):
        self.sample_repo: IWritingSampleRepository = sample_repo

    async def execute(self, sample_id: uuid.UUID, approved: bool) -> WritingSampleEntity:
        sample = self.sample_repo.get(sample_id)
        if not sample:
            raise NotFoundException(f"Writing sample {sample_id} not found")
        sample.approved_as_style_example = approved
        return self.sample_repo.update(sample)


class DeleteSampleUsecase:
    def __init__(self, sample_repo: IWritingSampleRepoDep, vector_store: IVectorStoreDep):
        self.sample_repo: IWritingSampleRepository = sample_repo
        self.vector_store: IVectorStore = vector_store

    async def execute(self, sample_id: uuid.UUID) -> bool:
        sample = self.sample_repo.get(sample_id)
        if not sample:
            raise NotFoundException(f"Writing sample {sample_id} not found")
        await self.vector_store.delete_chunks_by_sample_id(sample_id)
        return self.sample_repo.delete(sample_id)


ListSamplesUsecaseDep = Annotated[ListSamplesUsecase, Depends(ListSamplesUsecase)]
ToggleSampleApprovalUsecaseDep = Annotated[ToggleSampleApprovalUsecase, Depends(ToggleSampleApprovalUsecase)]
DeleteSampleUsecaseDep = Annotated[DeleteSampleUsecase, Depends(DeleteSampleUsecase)]
