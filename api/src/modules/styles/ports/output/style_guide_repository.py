from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import StyleGuideEntity


class IStyleGuideRepository(ABC):
    @abstractmethod
    def latest(self) -> StyleGuideEntity | None:
        pass

    @abstractmethod
    def create(self, guide: StyleGuideEntity) -> StyleGuideEntity:
        pass

    @abstractmethod
    def count(self) -> int:
        pass
