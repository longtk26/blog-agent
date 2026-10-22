import asyncio
from typing import Callable, TypeVar

from sqlmodel import Session

from src.libs.database.session import db_session_manager

T = TypeVar("T")


def run_in_session(fn: Callable[[Session], T]) -> T:
    """Run `fn` in a fresh session and commit; for code outside an HTTP request (graph nodes, runners, streams)."""
    with Session(db_session_manager.engine, expire_on_commit=False) as session:
        try:
            result = fn(session)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise


async def arun_in_session(fn: Callable[[Session], T]) -> T:
    # SQLModel sessions are sync; keep blocking DB I/O off the event loop.
    return await asyncio.to_thread(run_in_session, fn)
