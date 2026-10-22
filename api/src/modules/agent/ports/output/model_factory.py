from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from langchain_core.language_models import BaseChatModel


class ModelRole(StrEnum):
    PLANNER = "planner"
    WRITER = "writer"
    FAST = "fast"
    JUDGE = "judge"


@dataclass(frozen=True)
class ModelSpec:
    role: ModelRole
    model: str | None
    temperature: float
    max_tokens: int
    timeout_seconds: float
    max_retries: int

    @property
    def provider(self) -> str | None:
        return self.model.split(":", 1)[0] if self.model else None


class IModelFactory(ABC):
    @abstractmethod
    def spec(self, role: ModelRole) -> ModelSpec:
        pass

    @abstractmethod
    def get(self, role: ModelRole) -> BaseChatModel:
        """Return a configured chat model; raises LLM_NOT_CONFIGURED if the role has no model."""
        pass

    def is_configured(self, role: ModelRole) -> bool:
        return self.spec(role).model is not None

    def describe(self) -> dict[str, str | None]:
        return {role.value: self.spec(role).model for role in ModelRole}
