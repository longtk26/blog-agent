from abc import ABC, abstractmethod

from pydantic import BaseModel


class SearchResult(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    score: float | None = None
    published_date: str | None = None


class SearchError(Exception):
    pass


class ISearchProvider(ABC):
    name: str

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        pass
