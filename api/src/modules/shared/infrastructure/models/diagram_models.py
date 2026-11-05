from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Column, ForeignKey, Text
from sqlmodel import Field, SQLModel

from src.modules.shared.infrastructure.models._columns import jsonb_column, timestamp_column, utcnow


class DiagramAssetModel(SQLModel, table=True):
    __tablename__ = "diagram_assets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(foreign_key="writing_tasks.id", index=True, nullable=False)
    article_revision_id: uuid.UUID | None = Field(default=None, foreign_key="article_revisions.id", index=True, nullable=True)
    slot_id: str = Field(max_length=64, index=True)
    format: str = Field(max_length=16)  # "drawio" | "mermaid"
    spec: dict[str, Any] = Field(default_factory=dict, sa_column=jsonb_column(nullable=False))
    source_path: str = Field(sa_column=Column(Text, nullable=False))
    svg_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    png_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    sha256: str = Field(max_length=64, index=True, default="")
    validation_status: str = Field(default="valid", max_length=16)  # "valid" | "warning" | "error"
    review: dict[str, Any] | None = Field(default=None, sa_column=jsonb_column(nullable=True))
    review_rounds: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
