from dataclasses import dataclass
from typing import Protocol
import uuid


@dataclass
class VectorChunk:
    id: uuid.UUID
    sample_id: uuid.UUID | None = None
    note_id: uuid.UUID | None = None
    chunk_index: int = 0
    heading_path: str = ""
    content: str = ""
    chunk_type: str = "section"  # "section" | "outline" | "note"
    embedding: list[float] | None = None


@dataclass
class VectorSearchResult:
    chunk: VectorChunk
    similarity: float  # 1.0 - cosine_distance
    sample_title: str | None = None
    origin: str | None = None
    remote_id: str | None = None
    citable_url: str | None = None
    quality_score: float | None = None


class IVectorStore(Protocol):
    """Output port for vector storage and semantic search using pgvector."""

    async def upsert_chunks(self, chunks: list[VectorChunk]) -> None:
        """Upsert embedded chunks into the vector store."""
        ...

    async def delete_chunks_by_sample_id(self, sample_id: uuid.UUID) -> None:
        """Remove all chunks associated with a writing sample."""
        ...

    async def delete_chunks_by_note_id(self, note_id: uuid.UUID) -> None:
        """Remove all chunks associated with an owner note."""
        ...

    async def get_chunks_by_ids(self, chunk_ids: list[uuid.UUID]) -> list[VectorChunk]:
        """Fetch chunks by their UUIDs."""
        ...

    async def similarity_search(
        self,
        query_embedding: list[float],
        k: int = 5,
        chunk_type: str | None = None,
        sample_approved_only: bool = True,
        origin: str | None = None,
        exclude_sample_id: uuid.UUID | None = None,
    ) -> list[VectorSearchResult]:
        """Perform semantic similarity search using cosine distance."""
        ...
