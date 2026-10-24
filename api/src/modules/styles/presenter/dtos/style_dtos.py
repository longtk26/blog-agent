from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field


class ImportSamplesRequestDto(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["sanity", "local"])


class ImportSamplesResponseDto(BaseModel):
    imported: int
    updated: int
    skipped: int
    total_chunks: int


class WritingSampleResponseDto(BaseModel):
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


class ToggleApprovalRequestDto(BaseModel):
    approved: bool


class StyleProfileResponseDto(BaseModel):
    id: uuid.UUID | None
    version: int
    is_active: bool
    name: str
    source: str = "learned_profile"
    profile_data: dict[str, Any]
    markdown_content: str | None
    created_at: datetime | None
    updated_at: datetime | None


class GenerateStyleProfileRequestDto(BaseModel):
    name: str | None = None


class UpdateStyleProfileRequestDto(BaseModel):
    name: str | None = None
    profile_data: dict[str, Any] | None = None
    markdown_content: str | None = None


class OwnerNoteRequestDto(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1)
    citable_url: str | None = None
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)


class OwnerNoteResponseDto(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    citable_url: str | None
    quality_score: float
    created_at: datetime | None
    updated_at: datetime | None
