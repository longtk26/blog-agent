from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def jsonb_column(nullable: bool = False) -> Column:
    return Column(JSONB, nullable=nullable)


def timestamp_column(nullable: bool = False, index: bool = False) -> Column:
    return Column(DateTime(timezone=True), nullable=nullable, index=index)
