"""Domain entity for diagram assets (E7-S6)."""

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

from src.modules.shared.infrastructure.models._columns import utcnow


class DiagramAssetEntity(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: uuid.UUID
    article_revision_id: uuid.UUID | None = None
    slot_id: str
    format: Literal["drawio", "mermaid"] = "drawio"
    spec: dict[str, Any] = Field(default_factory=dict)
    source_path: str
    svg_path: str | None = None
    png_path: str | None = None
    sha256: str = ""
    validation_status: str = "valid"  # valid | warning | error
    # E10-S7 visual review of the published render: {status, passed, major, minor, issues[], lint[]}
    review: dict[str, Any] | None = None
    review_rounds: int = 0            # generations tried for this slot (1 = no repair needed)
    created_at: datetime = Field(default_factory=utcnow)
