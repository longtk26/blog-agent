from datetime import datetime
from typing import Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from src.configs.config import config
from src.modules.shared.infrastructure.models._columns import jsonb_column, timestamp_column, utcnow


class WritingSampleModel(SQLModel, table=True):
    __tablename__ = "writing_samples"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    origin: str = Field(index=True)  # "sanity" | "local"
    remote_id: str = Field(index=True)  # Sanity _id or relative file path
    title: str = Field(sa_column=Column(Text, nullable=False))
    tags: list[str] = Field(default_factory=list, sa_column=jsonb_column(nullable=False))
    published_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True, index=True))
    approved_as_style_example: bool = Field(default=True, index=True)
    content: str = Field(sa_column=Column(Text, nullable=False))
    content_hash: str = Field(sa_column=Column(Text, index=True, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class SampleChunkModel(SQLModel, table=True):
    __tablename__ = "sample_chunks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sample_id: uuid.UUID | None = Field(default=None, foreign_key="writing_samples.id", ondelete="CASCADE", index=True)
    note_id: uuid.UUID | None = Field(default=None, foreign_key="owner_notes.id", ondelete="CASCADE", index=True)
    chunk_index: int = Field(default=0)
    heading_path: str = Field(default="", sa_column=Column(Text, nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    chunk_type: str = Field(default="section", index=True)  # "section" | "outline" | "note"
    embedding: Any = Field(default=None, sa_column=Column(Vector(config.embedding_dim), nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class StyleProfileModel(SQLModel, table=True):
    __tablename__ = "style_profiles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version: int = Field(default=1, index=True)
    is_active: bool = Field(default=False, index=True)
    name: str = Field(default="Default Profile")
    profile_data: dict[str, Any] = Field(default_factory=dict, sa_column=jsonb_column(nullable=False))
    markdown_content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class OwnerNoteModel(SQLModel, table=True):
    __tablename__ = "owner_notes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(sa_column=Column(Text, nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    citable_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    quality_score: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
