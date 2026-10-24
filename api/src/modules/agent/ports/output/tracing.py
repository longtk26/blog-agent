import uuid
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig


class ITracing(ABC):
    enabled: bool
    project: str

    @abstractmethod
    def run_config(
        self,
        *,
        run_name: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: uuid.UUID | None = None,
        callbacks: list[BaseCallbackHandler] | None = None,
        configurable: dict[str, Any] | None = None,
    ) -> RunnableConfig:
        """Build the RunnableConfig every graph/model invocation must use."""
        pass

    @abstractmethod
    async def run_url(self, run_id: uuid.UUID | str) -> str | None:
        pass

    @abstractmethod
    def record_feedback(
        self, run_id: uuid.UUID | str, key: str, *, score: float | None = None, comment: str | None = None, value: Any = None
    ) -> None:
        """Attach human feedback (review decisions) to a traced run; a no-op when tracing is off."""
        pass

    @abstractmethod
    def flush(self) -> None:
        pass
