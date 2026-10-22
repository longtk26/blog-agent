import asyncio

from src.modules.research.ports.output import ISearchProvider, SearchError, SearchResult


class DuckDuckGoSearchProvider(ISearchProvider):
    """Keyless fallback for local use. Less reliable and rate-limited; prefer Tavily for real research."""

    name = "duckduckgo"

    def __init__(self, timeout_seconds: float):
        self.timeout = timeout_seconds

    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        terms = [query]
        if include_domains:
            terms.append("(" + " OR ".join(f"site:{d}" for d in include_domains) + ")")
        terms.extend(f"-site:{d}" for d in exclude_domains or [])

        def run() -> list[dict]:
            from ddgs import DDGS

            return DDGS(timeout=int(self.timeout)).text(" ".join(terms), max_results=max_results)

        try:
            rows = await asyncio.to_thread(run)
        except Exception as exc:
            raise SearchError(f"DuckDuckGo search failed: {type(exc).__name__}") from exc
        return [
            SearchResult(url=row["href"], title=row.get("title"), snippet=row.get("body"))
            for row in rows or []
            if row.get("href")
        ]
