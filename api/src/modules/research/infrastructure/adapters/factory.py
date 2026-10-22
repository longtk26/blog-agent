from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.configs import config as app_config
from src.configs.config import Config
from src.modules.research.infrastructure.adapters.chained_extractor import ChainedPageExtractor
from src.modules.research.infrastructure.adapters.duckduckgo import DuckDuckGoSearchProvider
from src.modules.research.infrastructure.adapters.http_extractor import HttpPageExtractor
from src.modules.research.infrastructure.adapters.tavily import TavilyPageExtractor, TavilySearchProvider
from src.modules.research.ports.output import IPageExtractor, ISearchProvider


def build_search_provider(config: Config) -> ISearchProvider:
    if config.resolved_search_provider == "tavily":
        if config.tavily_api_key is None:
            raise ValueError("SEARCH_PROVIDER=tavily requires TAVILY_API_KEY")
        return TavilySearchProvider(config.tavily_api_key.get_secret_value(), config.fetch_timeout_seconds * 2)
    return DuckDuckGoSearchProvider(config.fetch_timeout_seconds)


def build_page_extractor(config: Config) -> IPageExtractor:
    http = HttpPageExtractor(config.fetch_timeout_seconds, config.fetch_max_bytes, config.fetch_allow_private_hosts)
    if config.tavily_api_key is not None:
        tavily = TavilyPageExtractor(
            config.tavily_api_key.get_secret_value(), config.fetch_timeout_seconds * 2, config.fetch_allow_private_hosts
        )
        return ChainedPageExtractor([tavily, http])
    return http


@lru_cache
def get_search_provider() -> ISearchProvider:
    return build_search_provider(app_config)


@lru_cache
def get_page_extractor() -> IPageExtractor:
    return build_page_extractor(app_config)


ISearchProviderDep = Annotated[ISearchProvider, Depends(get_search_provider)]
