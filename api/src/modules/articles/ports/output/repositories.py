import uuid
from abc import ABC, abstractmethod

from src.modules.shared.domain.entities import ArticleDraftEntity, ArticleRevisionEntity, EvaluationResultEntity


class IDraftRepository(ABC):
    @abstractmethod
    def get(self, task_id: uuid.UUID) -> ArticleDraftEntity | None:
        pass

    @abstractmethod
    def save(self, draft: ArticleDraftEntity) -> ArticleDraftEntity:
        pass


class IRevisionRepository(ABC):
    @abstractmethod
    def create(self, revision: ArticleRevisionEntity) -> ArticleRevisionEntity:
        pass

    @abstractmethod
    def get(self, revision_id: uuid.UUID) -> ArticleRevisionEntity | None:
        pass

    @abstractmethod
    def list_by_task(self, task_id: uuid.UUID) -> list[ArticleRevisionEntity]:
        pass

    @abstractmethod
    def latest(self, task_id: uuid.UUID) -> ArticleRevisionEntity | None:
        pass

    @abstractmethod
    def slug_taken(self, slug: str, exclude_task_id: uuid.UUID) -> bool:
        pass


class IEvaluationRepository(ABC):
    @abstractmethod
    def add_many(self, results: list[EvaluationResultEntity]) -> list[EvaluationResultEntity]:
        pass

    @abstractmethod
    def list_by_revision(self, revision_id: uuid.UUID) -> list[EvaluationResultEntity]:
        pass
