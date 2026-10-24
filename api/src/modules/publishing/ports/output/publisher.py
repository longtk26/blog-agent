import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from src.modules.shared.domain.entities import ArticleRevisionEntity, PublicationTarget


@dataclass
class PublishOutcome:
    destination: PublicationTarget | str
    remote_document_id: str
    remote_url: str
    rendered_content_hash: str
    studio_url: str | None = None
    rendered_markdown: str | None = None


class PublishError(Exception):
    def __init__(self, message: str, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class IPublisher(ABC):
    @property
    @abstractmethod
    def destination(self) -> PublicationTarget:
        ...

    @abstractmethod
    async def publish(
        self,
        task_id: uuid.UUID,
        revision: ArticleRevisionEntity,
        existing_remote_id: str | None = None,
        on_asset_uploaded: Callable[[str, str, str], None] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PublishOutcome:
        """Publish revision. Raises PublishError or conflict/validation exceptions."""
        ...

    @abstractmethod
    async def unpublish(self, remote_document_id: str) -> None:
        """Unpublish/delete document from destination."""
        ...
