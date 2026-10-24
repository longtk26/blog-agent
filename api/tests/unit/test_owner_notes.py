import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.modules.shared.domain.entities import OwnerNoteEntity
from src.modules.styles.usecases.owner_note_usecases import (
    CreateOwnerNoteUsecase,
    UpdateOwnerNoteUsecase,
    DeleteOwnerNoteUsecase,
    ListOwnerNotesUsecase,
)


@pytest.fixture
def note_repo():
    repo = MagicMock()
    return repo


@pytest.fixture
def vector_store():
    store = MagicMock()
    store.upsert_chunks = AsyncMock()
    store.delete_chunks_by_note_id = AsyncMock()
    return store


@pytest.fixture
def embedding_service():
    service = MagicMock()
    service.dimension = 768
    service.embed_documents = AsyncMock(return_value=[[0.1] * 768])
    return service


@pytest.mark.asyncio
async def test_create_owner_note(note_repo, vector_store, embedding_service):
    note_id = uuid.uuid4()
    saved_note = OwnerNoteEntity(
        id=note_id,
        title="Personal Benchmark Results",
        content="## Measurements\n\nThroughput was 150 tokens/sec on A100.",
        citable_url=None,
        quality_score=1.0,
    )
    note_repo.create.return_value = saved_note

    usecase = CreateOwnerNoteUsecase(
        note_repo=note_repo,
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    created = await usecase.execute(
        title="Personal Benchmark Results",
        content="## Measurements\n\nThroughput was 150 tokens/sec on A100.",
    )

    assert created.id == note_id
    note_repo.create.assert_called_once()
    vector_store.upsert_chunks.assert_called_once()
    embedding_service.embed_documents.assert_called_once()


@pytest.mark.asyncio
async def test_update_owner_note(note_repo, vector_store, embedding_service):
    note_id = uuid.uuid4()
    existing = OwnerNoteEntity(
        id=note_id,
        title="Old Title",
        content="Old content",
        citable_url=None,
        quality_score=0.9,
    )
    note_repo.get.return_value = existing
    note_repo.update.return_value = existing

    usecase = UpdateOwnerNoteUsecase(
        note_repo=note_repo,
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    updated = await usecase.execute(
        note_id=note_id,
        title="New Title",
        content="New content",
        citable_url="https://internal-docs.com/notes/1",
        quality_score=1.0,
    )

    vector_store.delete_chunks_by_note_id.assert_called_once_with(note_id)
    vector_store.upsert_chunks.assert_called_once()
    assert updated.title == "New Title"


@pytest.mark.asyncio
async def test_delete_owner_note(note_repo, vector_store):
    note_id = uuid.uuid4()
    existing = OwnerNoteEntity(
        id=note_id,
        title="Note",
        content="Content",
    )
    note_repo.get.return_value = existing
    note_repo.delete.return_value = True

    usecase = DeleteOwnerNoteUsecase(
        note_repo=note_repo,
        vector_store=vector_store,
    )

    result = await usecase.execute(note_id)
    assert result is True
    vector_store.delete_chunks_by_note_id.assert_called_once_with(note_id)
    note_repo.delete.assert_called_once_with(note_id)
