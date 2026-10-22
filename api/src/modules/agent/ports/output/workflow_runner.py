from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any


class ThreadStatus(StrEnum):
    NONE = "none"                # no checkpoint yet
    PENDING = "pending"          # stopped mid-way (failure/restart); can resume
    INTERRUPTED = "interrupted"  # paused at an interrupt (awaiting owner input)
    FINISHED = "finished"        # reached END


class IWorkflowRunner(ABC):
    """Use cases start/resume/cancel the LangGraph workflow only through this port."""

    @abstractmethod
    async def start(self, task_id: str) -> None:
        pass

    @abstractmethod
    async def resume(self, task_id: str, command: dict[str, Any] | None = None) -> None:
        """Continue from the last checkpoint; `command` is passed to a pending interrupt."""
        pass

    @abstractmethod
    async def cancel(self, task_id: str) -> None:
        pass

    @abstractmethod
    def is_running(self, task_id: str) -> bool:
        pass

    @abstractmethod
    async def thread_status(self, task_id: str) -> ThreadStatus:
        pass

    @abstractmethod
    async def pending_interrupt(self, task_id: str) -> dict | None:
        """Value of the interrupt the thread is paused at (e.g. {"type": "awaiting_review", ...}), if any."""
        pass
