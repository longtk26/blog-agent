from abc import ABC, abstractmethod

from pydantic import BaseModel


class ExtractedPage(BaseModel):
    url: str
    final_url: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    text: str


class ExtractionError(Exception):
    pass


class IPageExtractor(ABC):
    name: str

    @abstractmethod
    async def extract(self, url: str) -> ExtractedPage:
        """Fetch and extract readable text; raises ExtractionError."""
        pass
