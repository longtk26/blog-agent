from .source_repository import ISourceRepository
from .claim_repository import IClaimRepository
from .brief_repository import IBriefRepository
from .search_provider import ISearchProvider, SearchResult, SearchError
from .page_extractor import IPageExtractor, ExtractedPage, ExtractionError

# Dep bindings live in infrastructure; re-exported lazily so adapters can import these ports without a cycle.
_DEPS = {
    "ISourceRepoDep": "persistence",
    "IClaimRepoDep": "persistence",
    "IBriefRepoDep": "persistence",
    "ISearchProviderDep": "adapters",
}


def __getattr__(name: str):
    if name in _DEPS:
        from importlib import import_module

        return getattr(import_module(f"src.modules.research.infrastructure.{_DEPS[name]}"), name)
    raise AttributeError(name)


__all__ = [
    "ISourceRepository",
    "IClaimRepository",
    "IBriefRepository",
    "ISearchProvider",
    "SearchResult",
    "SearchError",
    "IPageExtractor",
    "ExtractedPage",
    "ExtractionError",
    "ISourceRepoDep",
    "IClaimRepoDep",
    "IBriefRepoDep",
    "ISearchProviderDep",
]
