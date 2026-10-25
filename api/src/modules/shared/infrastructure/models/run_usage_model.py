import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from ._columns import timestamp_column, utcnow


class RunUsageModel(SQLModel, table=True):
    __tablename__ = "run_usage"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(foreign_key="writing_tasks.id", index=True, ondelete="CASCADE")
    run_id: uuid.UUID | None = Field(default=None, index=True)
    node: str = Field(max_length=64, index=True)
    model: str = Field(max_length=128, index=True)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    cached_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    latency_ms: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
