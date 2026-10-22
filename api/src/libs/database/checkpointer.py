import re
from typing import Annotated

import psycopg
from fastapi import Depends, Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.configs.logger import get_logger
from src.libs.database.session import to_libpq_url

logger = get_logger(__name__)

SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


class CheckpointerManager:
    """Owns the psycopg pool and the LangGraph AsyncPostgresSaver.

    Checkpoint tables live in their own schema (default `langgraph`) and are managed by
    LangGraph's `setup()`, not by Alembic.
    """

    def __init__(self, db_url: str, schema: str = "langgraph", max_size: int = 5):
        if not SCHEMA_NAME.match(schema):
            raise ValueError(f"Invalid checkpoint schema name: {schema!r}")
        self.conninfo = to_libpq_url(db_url)
        self.schema = schema
        self.max_size = max_size
        self.pool: AsyncConnectionPool | None = None
        self.saver: AsyncPostgresSaver | None = None

    async def open(self) -> AsyncPostgresSaver:
        async with await psycopg.AsyncConnection.connect(self.conninfo, autocommit=True) as conn:
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')

        self.pool = AsyncConnectionPool(
            self.conninfo,
            max_size=self.max_size,
            open=False,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
                "options": f"-c search_path={self.schema}",
            },
        )
        await self.pool.open(wait=True, timeout=30)
        self.saver = AsyncPostgresSaver(self.pool)
        await self.saver.setup()
        logger.info("Checkpointer ready", extra={"context": {"schema": self.schema}})
        return self.saver

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
        self.pool = None
        self.saver = None

    async def ping(self) -> bool:
        if self.pool is None:
            return False
        try:
            async with self.pool.connection(timeout=5) as conn:
                await conn.execute("SELECT 1 FROM checkpoint_migrations LIMIT 1")
            return True
        except Exception:
            return False


def get_checkpointer_manager(request: Request) -> CheckpointerManager:
    return request.app.state.checkpointer_manager


def get_checkpointer(request: Request) -> BaseCheckpointSaver:
    return get_checkpointer_manager(request).saver


CheckpointerManagerDep = Annotated[CheckpointerManager, Depends(get_checkpointer_manager)]
CheckpointerDep = Annotated[BaseCheckpointSaver, Depends(get_checkpointer)]
