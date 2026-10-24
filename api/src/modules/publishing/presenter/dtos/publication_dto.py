from typing import Any
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.modules.shared.domain.entities import PublicationEntity, PublicationTarget


class PublishRequestDto(BaseModel):
    model_config = ConfigDict(extra="ignore")

    destinations: list[PublicationTarget] = Field(
        default_factory=lambda: [PublicationTarget.SANITY], min_length=1
    )
    options: dict[str, Any] = Field(default_factory=dict)


class UnpublishRequestDto(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slug: str = Field(min_length=1, max_length=120)
    destinations: list[PublicationTarget] = Field(
        default_factory=lambda: [PublicationTarget.SANITY], min_length=1
    )


class PublicationDto(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    article_revision_id: uuid.UUID
    destination: PublicationTarget | str
    remote_document_id: str | None = None
    remote_url: str | None = None
    destination_id: str | None = None
    destination_url: str | None = None
    status: str
    attempt_count: int
    rendered_content_hash: str | None = None
    last_error: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_entity(cls, entity: PublicationEntity) -> "PublicationDto":
        return cls(
            id=entity.id or uuid.uuid4(),
            task_id=entity.task_id,
            article_revision_id=entity.article_revision_id,
            destination=entity.destination,
            remote_document_id=entity.remote_document_id,
            remote_url=entity.remote_url,
            destination_id=entity.remote_document_id,
            destination_url=entity.remote_url,
            status=str(entity.status),
            attempt_count=entity.attempt_count,
            rendered_content_hash=entity.rendered_content_hash,
            last_error=entity.last_error,
            published_at=entity.published_at,
            updated_at=entity.updated_at,
        )


class PublicationListResponseDto(BaseModel):
    items: list[PublicationDto]
