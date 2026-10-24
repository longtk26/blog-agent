import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.configs.config import config
from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.nodes.writing import WritingNodes
from src.modules.shared.domain.entities import (
    ArticleDraftEntity,
    DraftSection,
    WritingTaskEntity,
    ResearchBriefEntity,
)
from src.modules.styles.ports.output.vector_store import VectorChunk, VectorSearchResult


@pytest.fixture
def mock_deps():
    store = MagicMock()
    models = MagicMock()
    search = MagicMock()
    extractor = MagicMock()
    vector_store = MagicMock()
    embeddings = MagicMock()

    embeddings.embed_query = AsyncMock(return_value=[0.1] * 768)

    sample_chunk_id = uuid.uuid4()
    search_result = VectorSearchResult(
        chunk=VectorChunk(
            id=sample_chunk_id,
            sample_id=uuid.uuid4(),
            chunk_index=0,
            heading_path="Overview",
            content="- Heading 1: Explain concept\n- Heading 2: Implementation",
            chunk_type="outline",
        ),
        similarity=0.92,
        sample_title="LoRA Fine-Tuning Guide",
        origin="sanity",
        remote_id="sanity_post_1",
    )
    vector_store.similarity_search = AsyncMock(return_value=[search_result])
    vector_store.get_chunks_by_ids = AsyncMock(return_value=[search_result.chunk])

    store.style_guide = AsyncMock(return_value=("profile-v1", "# Style Guide"))
    store.get_valid_post_ids = AsyncMock(return_value={"sanity_post_1"})
    store.list_sources = AsyncMock(return_value=[])
    store.list_claims = AsyncMock(return_value=[])
    store.update_task = AsyncMock()
    store.transition = AsyncMock()
    store.get_draft = AsyncMock(return_value=None)
    store.save_draft = AsyncMock()
    store.slug_taken = AsyncMock(return_value=False)

    return WorkflowDeps(
        store=store,
        models=models,
        search=search,
        extractor=extractor,
        settings=config,
        vector_store=vector_store,
        embeddings=embeddings,
    )


@pytest.mark.asyncio
async def test_outline_retrieval_enabled(mock_deps):
    task_id = uuid.uuid4()
    task = WritingTaskEntity(
        id=task_id,
        topic="Modern Fine-Tuning",
        format="concept",
        use_style_examples=True,
    )
    mock_deps.store.get_task = AsyncMock(return_value=task)
    mock_deps.store.get_brief = AsyncMock(return_value=ResearchBriefEntity(task_id=task_id, markdown="", data={"summary": ""}))

    nodes = WritingNodes(mock_deps)

    from src.modules.agent.schemas.writing import OutlineOut, OutlineSectionOut

    mock_outline_out = OutlineOut(
        title_options=["Modern Fine-Tuning Guide"],
        angle="practical overview",
        intro_goal="Introduce modern fine-tuning methods",
        next_steps="Try running LoRA",
        requirement_map=[],
        sections=[
            OutlineSectionOut(heading="Background", goal="Explain background", est_words=200, key_points=["Point 1"]),
        ],
    )

    with patch("src.modules.agent.nodes.writing.invoke_structured", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_outline_out
        state = {"task_id": str(task_id)}
        result = await nodes.outline(state)

        assert "retrieved_style_chunk_ids" in result
        assert len(result["retrieved_style_chunk_ids"]) == 1
        mock_deps.embeddings.embed_query.assert_called_once()
        mock_deps.vector_store.similarity_search.assert_called_once()


@pytest.mark.asyncio
async def test_outline_retrieval_disabled(mock_deps):
    task_id = uuid.uuid4()
    task = WritingTaskEntity(
        id=task_id,
        topic="Modern Fine-Tuning",
        format="concept",
        use_style_examples=False,
    )
    mock_deps.store.get_task = AsyncMock(return_value=task)
    mock_deps.store.get_brief = AsyncMock(return_value=ResearchBriefEntity(task_id=task_id, markdown="", data={"summary": ""}))

    nodes = WritingNodes(mock_deps)

    from src.modules.agent.schemas.writing import OutlineOut, OutlineSectionOut

    mock_outline_out = OutlineOut(
        title_options=["Modern Fine-Tuning Guide"],
        angle="practical overview",
        intro_goal="Introduce modern fine-tuning methods",
        next_steps="Try running LoRA",
        requirement_map=[],
        sections=[
            OutlineSectionOut(heading="Background", goal="Explain background", est_words=200, key_points=["Point 1"]),
        ],
    )

    with patch("src.modules.agent.nodes.writing.invoke_structured", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_outline_out
        state = {"task_id": str(task_id)}
        result = await nodes.outline(state)

        assert result["retrieved_style_chunk_ids"] == []
        mock_deps.embeddings.embed_query.assert_not_called()
        mock_deps.vector_store.similarity_search.assert_not_called()
