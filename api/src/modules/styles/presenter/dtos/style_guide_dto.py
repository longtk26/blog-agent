from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StyleGuideResponseDto(BaseModel):
    version: str
    content: str
    source: Literal["seed", "owner"]
    updated_at: datetime | None


class UpdateStyleGuideRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=50, max_length=20000)
