import uuid
from datetime import datetime

from sqlalchemy import Text
from sqlmodel import Column, Field, SQLModel

from ._columns import jsonb_column, timestamp_column, utcnow


class WritingTaskModel(SQLModel, table=True):
    __tablename__ = "writing_tasks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topic: str = Field(max_length=500)
    mode: str = Field(max_length=32, index=True)
    audience: str | None = Field(default=None, max_length=300)
    depth: str = Field(max_length=32)
    language: str = Field(default="en", max_length=16)
    format: str = Field(max_length=32)
    series: dict | None = Field(default=None, sa_column=jsonb_column(nullable=True))
    requirements: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    angle: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    include_diagram: str = Field(default="auto", max_length=16)
    diagram_format: str = Field(default="auto", max_length=16)
    review_outline: bool = False
    use_style_examples: bool = True
    publication_targets: list = Field(default_factory=list, sa_column=jsonb_column())
    budgets: dict = Field(default_factory=dict, sa_column=jsonb_column())

    status: str = Field(max_length=32, index=True)
    failed_stage: str | None = Field(default=None, max_length=32)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    resumable: bool = False
    research_plan: dict | None = Field(default=None, sa_column=jsonb_column(nullable=True))
    outline: dict | None = Field(default=None, sa_column=jsonb_column(nullable=True))
    open_questions: list = Field(default_factory=list, sa_column=jsonb_column())
    progress: dict = Field(default_factory=dict, sa_column=jsonb_column())
    last_run_id: uuid.UUID | None = None

    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
