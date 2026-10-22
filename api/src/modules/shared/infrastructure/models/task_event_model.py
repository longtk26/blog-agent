import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index
from sqlmodel import Column, Field, SQLModel

from ._columns import jsonb_column, timestamp_column, utcnow


class TaskEventModel(SQLModel, table=True):
    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task_id_id", "task_id", "id"),)

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    task_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False)
    )
    type: str = Field(max_length=64)
    from_status: str | None = Field(default=None, max_length=32)
    to_status: str | None = Field(default=None, max_length=32)
    actor: str = Field(default="system", max_length=16)
    payload: dict = Field(default_factory=dict, sa_column=jsonb_column())
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
