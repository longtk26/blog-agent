import asyncio
import logging
import os
from typing import Annotated

from fastapi import Depends
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings

from src.configs.config import config
from src.modules.styles.ports.output.embedding_service import IEmbeddingService

logger = logging.getLogger(__name__)


class LangChainEmbeddingService(IEmbeddingService):
    """Embedding service using LangChain's init_embeddings."""

    def __init__(
        self,
        model: str | None = None,
        dimension: int | None = None,
        embeddings: Embeddings | None = None,
    ):
        self._model = model or config.embedding_model or "google_genai:gemini-embedding-001"
        self._dim = dimension or config.embedding_dim or 768
        self._embeddings = embeddings

    @property
    def dimension(self) -> int:
        return self._dim

    def _get_client(self) -> Embeddings:
        if self._embeddings is not None:
            return self._embeddings

        # Ensure provider API key is in env if configured in settings
        provider, _, _ = self._model.partition(":")
        if provider == "google_genai" and config.google_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", config.google_api_key.get_secret_value())
        elif provider == "openai" and config.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", config.openai_api_key.get_secret_value())

        kwargs: dict = {}
        if provider == "google_genai":
            kwargs["output_dimensionality"] = self._dim
        elif provider == "openai":
            kwargs["dimensions"] = self._dim

        self._embeddings = init_embeddings(self._model, **kwargs)
        return self._embeddings

    async def embed_query(self, text: str) -> list[float]:
        client = self._get_client()
        if hasattr(client, "aembed_query"):
            return await client.aembed_query(text)
        return await asyncio.to_thread(client.embed_query, text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        if hasattr(client, "aembed_documents"):
            return await client.aembed_documents(texts)
        return await asyncio.to_thread(client.embed_documents, texts)


_default_embedding_service: IEmbeddingService | None = None


def get_embedding_service() -> IEmbeddingService:
    global _default_embedding_service
    if _default_embedding_service is None:
        _default_embedding_service = LangChainEmbeddingService()
    return _default_embedding_service


IEmbeddingServiceDep = Annotated[IEmbeddingService, Depends(get_embedding_service)]
