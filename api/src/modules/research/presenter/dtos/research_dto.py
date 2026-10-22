import uuid
from datetime import datetime

from pydantic import BaseModel

from src.modules.shared.domain.entities import ResearchClaimEntity, ResearchSourceEntity, SourceStatus, SourceType


class ClaimDto(BaseModel):
    id: uuid.UUID
    question_id: str | None
    text: str
    supporting_quote: str
    quote_verified: bool

    @classmethod
    def from_entity(cls, claim: ResearchClaimEntity) -> "ClaimDto":
        return cls(**claim.model_dump(include=set(cls.model_fields)))


class SourceDto(BaseModel):
    id: uuid.UUID
    url: str
    canonical_url: str
    title: str | None
    publisher: str | None
    published_at: str | None
    retrieved_at: datetime | None
    snippet: str | None
    query: str | None
    round: int
    status: SourceStatus
    source_type: SourceType | None
    quality_score: float | None
    quality_rationale: str | None
    relevance: float | None
    notes: list[str]
    error: str | None
    claims: list[ClaimDto]

    @classmethod
    def from_entity(cls, source: ResearchSourceEntity, claims: list[ResearchClaimEntity]) -> "SourceDto":
        data = source.model_dump(include=set(cls.model_fields) - {"claims"})
        return cls(**data, claims=[ClaimDto.from_entity(c) for c in claims])


class SourceListResponseDto(BaseModel):
    items: list[SourceDto]
    total: int


class ResearchBriefResponseDto(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    markdown: str
    data: dict
    created_at: datetime
