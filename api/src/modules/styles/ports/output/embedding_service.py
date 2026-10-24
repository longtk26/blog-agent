from typing import Protocol


class IEmbeddingService(Protocol):
    """Output port for computing vector embeddings."""

    @property
    def dimension(self) -> int:
        """Returns the embedding vector dimension (e.g. 768)."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Generate embedding vector for a single query text."""
        ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple document texts."""
        ...
