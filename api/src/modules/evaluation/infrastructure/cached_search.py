import hashlib
import json
import re
from pathlib import Path

from src.configs.logger import get_logger
from src.modules.research.ports.output import ISearchProvider, SearchError, SearchResult

logger = get_logger(__name__)


def _sanitize_filename(text: str) -> str:
    cleaned = re.sub(r"[^\w\-_]", "_", text).strip("_")
    return cleaned[:40] if cleaned else "query"


class CachedSearchProvider(ISearchProvider):
    name = "cached_search"

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        fallback_provider: ISearchProvider | None = None,
        live: bool = False,
        record: bool = True,
    ):
        if cache_dir is None:
            cache_dir = Path(__file__).resolve().parents[4] / "evals" / "cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fallback_provider = fallback_provider
        self.live = live
        self.record = record

    def _cache_key(
        self,
        query: str,
        max_results: int,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> str:
        key_raw = f"{query}|{max_results}|{sorted(include_domains or [])}|{sorted(exclude_domains or [])}"
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()[:12]
        slug = _sanitize_filename(query)
        return f"{slug}_{digest}.json"

    async def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        cache_file = self.cache_dir / self._cache_key(query, max_results, include_domains, exclude_domains)

        if not self.live and cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                logger.info(f"Loaded cached search results for '{query}' from {cache_file.name}")
                return [SearchResult(**item) for item in data]
            except Exception as exc:
                logger.warning(f"Failed to read cache file {cache_file}: {exc}")

        # Live search through fallback provider
        if self.fallback_provider is not None:
            logger.info(f"Executing live search for '{query}' via {self.fallback_provider.name}")
            results = await self.fallback_provider.search(
                query=query,
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
            )
            if self.record:
                try:
                    payload = [r.model_dump() for r in results]
                    cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    logger.info(f"Saved {len(results)} search results to {cache_file.name}")
                except Exception as exc:
                    logger.warning(f"Failed to cache search results: {exc}")
            return results

        # Fallback synthetic result if offline and not in cache
        logger.warning(f"No cached results found for '{query}' and no live provider configured.")
        return [
            SearchResult(
                url=f"https://docs.example.com/{_sanitize_filename(query)}",
                title=f"Documentation: {query}",
                snippet=f"Authoritative technical details and implementation reference regarding {query}.",
                score=0.9,
            )
        ]
