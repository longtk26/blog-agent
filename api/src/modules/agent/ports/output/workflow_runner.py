from abc import ABC, abstractmethod
from typing import Any


class IWorkflowRunner(ABC):
    """Use cases start/resume/cancel the LangGraph workflow only through this port (implemented in Epic 2)."""

    @abstractmethod
    async def start(self, task_id: str) -> None:
        pass

    @abstractmethod
    async def resume(self, task_id: str, command: dict[str, Any] | None = None) -> None:
        pass

    @abstractmethod
    async def cancel(self, task_id: str) -> None:
        pass

    @abstractmethod
    def is_running(self, task_id: str) -> bool:
        pass
