from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.modules.research.ports.output import ISearchProvider


class WebSearchArgs(BaseModel):
    query: str = Field(description="Keyword search query", min_length=2, max_length=300)
    max_results: int = Field(default=5, ge=1, le=10)
    include_domains: list[str] | None = Field(default=None, max_length=10)
    exclude_domains: list[str] | None = Field(default=None, max_length=50)


def make_search_tool(provider: ISearchProvider) -> StructuredTool:
    """LangChain tool around the search port: validated args, and a tool span in LangSmith traces."""

    async def web_search(
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict]:
        results = await provider.search(query, max_results, include_domains, exclude_domains)
        return [result.model_dump() for result in results]

    return StructuredTool.from_function(
        coroutine=web_search,
        name="web_search",
        description=f"Search the web ({provider.name}) and return result URLs, titles and snippets.",
        args_schema=WebSearchArgs,
    )
