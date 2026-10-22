import httpx

from src.modules.research.infrastructure.adapters.safe_fetch import ensure_public_url
from src.modules.research.ports.output import (
    ExtractedPage,
    ExtractionError,
    IPageExtractor,
    ISearchProvider,
    SearchError,
    SearchResult,
)

TAVILY_API = "https://api.tavily.com"


class _TavilyClient:
    def __init__(self, api_key: str, timeout_seconds: float, retries: int = 2):
        self.api_key = api_key
        self.timeout = httpx.Timeout(timeout_seconds)
        self.retries = retries

    async def post(self, path: str, payload: dict) -> dict:
        transport = httpx.AsyncHTTPTransport(retries=self.retries)
        async with httpx.AsyncClient(base_url=TAVILY_API, timeout=self.timeout, transport=transport) as client:
            response = await client.post(path, json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(f"Tavily {path} HTTP {response.status_code}", request=response.request, response=response)
        return response.json()


class TavilySearchProvider(ISearchProvider):
    name = "tavily"

    def __init__(self, api_key: str, timeout_seconds: float):
        self.client = _TavilyClient(api_key, timeout_seconds)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        payload = {"query": query, "max_results": max_results, "search_depth": "basic"}
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        try:
            data = await self.client.post("/search", payload)
        except httpx.HTTPError as exc:
            raise SearchError(str(exc)) from exc
        return [
            SearchResult(
                url=item["url"],
                title=item.get("title"),
                snippet=item.get("content"),
                score=item.get("score"),
                published_date=item.get("published_date"),
            )
            for item in data.get("results", [])
            if item.get("url")
        ]


class TavilyPageExtractor(IPageExtractor):
    name = "tavily"

    def __init__(self, api_key: str, timeout_seconds: float, allow_private: bool = False):
        self.client = _TavilyClient(api_key, timeout_seconds)
        self.allow_private = allow_private

    async def extract(self, url: str) -> ExtractedPage:
        await ensure_public_url(url, self.allow_private)
        try:
            data = await self.client.post("/extract", {"urls": [url], "extract_depth": "basic"})
        except httpx.HTTPError as exc:
            raise ExtractionError(f"Tavily extract failed: {exc}") from exc
        results = data.get("results") or []
        if not results or not (results[0].get("raw_content") or "").strip():
            failed = (data.get("failed_results") or [{}])[0]
            raise ExtractionError(f"Tavily could not extract page: {failed.get('error', 'no content')}")
        return ExtractedPage(url=url, final_url=results[0].get("url") or url, text=results[0]["raw_content"])
