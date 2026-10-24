import asyncio
import functools
import time
import uuid
from typing import Any, Awaitable, Callable

from langgraph.config import get_stream_writer
from langgraph.errors import GraphBubbleUp

from src.configs.logger import Redactor, get_logger
from src.modules.agent.graph.state import BlogState
from src.modules.shared.domain.value_objects import TaskStatus

logger = get_logger(__name__)

NodeFn = Callable[[Any, BlogState], Awaitable[dict]]


class TaskCancelled(Exception):
    """The owner cancelled the task while the graph was running; stop quietly."""


class NodeFailed(Exception):
    pass


def safe_error(exc: BaseException, redactor: Redactor | None = None) -> str:
    message = f"{type(exc).__name__}: {str(exc)[:400]}".rstrip(": ")
    return redactor(message) if redactor else message


def emit(event_type: str, **payload: Any) -> None:
    """Custom stream event; the runner persists it to task_events and wakes SSE listeners."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    writer({"type": event_type, **payload})


def workflow_node(name: str, stage: TaskStatus | None, timeout_seconds: float | None = None, run_when_rejected: bool = False):
    """Wraps a node method: status bookkeeping, start/finish events, timeout, and failure capture.

    On failure the task becomes `failed` (resumable) with `failed_stage=stage` and the exception is re-raised,
    so the checkpoint stays at the last completed step and `retry` re-runs only this node.
    Interrupts (GraphBubbleUp) and cancellation pass straight through. Pause nodes set `run_when_rejected` so a
    rejection can be delivered to them and end the thread instead of leaving it suspended.
    """

    def decorator(fn: NodeFn):
        @functools.wraps(fn)
        async def wrapper(self, state: BlogState) -> dict:
            deps = self.deps
            task_id = uuid.UUID(state["task_id"])
            task = await deps.store.get_task(task_id)
            if task.status == TaskStatus.REJECTED and not run_when_rejected:
                raise TaskCancelled(str(task_id))
            if stage is not None and task.status != stage:
                await deps.store.transition(task_id, stage)

            emit("node_started", node=name)
            started = time.perf_counter()
            timeout = timeout_seconds or deps.settings.node_timeout_seconds
            try:
                result = await asyncio.wait_for(fn(self, state), timeout=timeout)
            except (GraphBubbleUp, asyncio.CancelledError, TaskCancelled):
                raise
            except Exception as exc:
                message = safe_error(exc, Redactor(deps.settings.secret_values()))
                logger.exception("Node failed", extra={"context": {"node": name}})
                emit("error", node=name, message=message)
                await deps.store.fail_task(task_id, stage or task.status, message)
                raise NodeFailed(f"{name}: {message}") from exc

            emit("node_finished", node=name, duration_ms=int((time.perf_counter() - started) * 1000))
            return result

        return wrapper

    return decorator
