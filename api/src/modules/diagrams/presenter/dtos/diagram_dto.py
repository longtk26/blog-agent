"""DTOs for diagram assets and operations (E7-S6, E7-S7)."""

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity


class DiagramAssetResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    article_revision_id: uuid.UUID | None = None
    slot_id: str
    format: Literal["drawio", "mermaid"]
    spec: dict[str, Any] = Field(default_factory=dict)
    source_path: str
    svg_path: str | None = None
    png_path: str | None = None
    sha256: str
    validation_status: str
    created_at: datetime
    source_url: str
    svg_url: str
    png_url: str | None = None

    @classmethod
    def from_entity(cls, entity: DiagramAssetEntity) -> "DiagramAssetResponseDto":
        base_asset_url = f"/assets/{entity.id}"
        return cls(
            id=entity.id,
            task_id=entity.task_id,
            article_revision_id=entity.article_revision_id,
            slot_id=entity.slot_id,
            format=entity.format,
            spec=entity.spec,
            source_path=entity.source_path,
            svg_path=entity.svg_path,
            png_path=entity.png_path,
            sha256=entity.sha256,
            validation_status=entity.validation_status,
            created_at=entity.created_at,
            source_url=f"{base_asset_url}?type=source",
            svg_url=f"{base_asset_url}?type=svg",
            png_url=f"{base_asset_url}?type=png" if entity.png_path else None,
        )


class SwitchFormatRequestDto(BaseModel):
    target_format: Literal["drawio", "mermaid"]


class RegenerateDiagramRequestDto(BaseModel):
    feedback: str = Field(default="", max_length=1000)
