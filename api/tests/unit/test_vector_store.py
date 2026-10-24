import uuid
import pytest
from unittest.mock import AsyncMock

from src.modules.styles.infrastructure.adapters.embedding_service_adapter import LangChainEmbeddingService
from src.modules.styles.infrastructure.adapters.vector_store_adapter import PgVectorStore
from src.modules.styles.ports.output.vector_store import VectorChunk


@pytest.mark.asyncio
async def test_embedding_service_mocked():
    mock_client = AsyncMock()
    mock_client.aembed_query.return_value = [0.1] * 768
    mock_client.aembed_documents.return_value = [[0.1] * 768, [0.2] * 768]

    service = LangChainEmbeddingService(embeddings=mock_client, dimension=768)
    assert service.dimension == 768

    q = await service.embed_query("test query")
    assert len(q) == 768
    assert q[0] == 0.1

    docs = await service.embed_documents(["doc1", "doc2"])
    assert len(docs) == 2
    assert len(docs[0]) == 768
    assert docs[1][0] == 0.2


def test_vector_chunk_dataclass():
    chunk_id = uuid.uuid4()
    sample_id = uuid.uuid4()
    chunk = VectorChunk(
        id=chunk_id,
        sample_id=sample_id,
        chunk_index=1,
        heading_path="1. Intro",
        content="Intro text",
        chunk_type="section",
        embedding=[0.0] * 768,
    )
    assert chunk.id == chunk_id
    assert chunk.chunk_type == "section"
    assert chunk.heading_path == "1. Intro"
