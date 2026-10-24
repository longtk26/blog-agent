from typing import Annotated
import uuid

from fastapi import Depends

from src.libs.exceptions import BadRequestException, NotFoundException
from src.modules.shared.domain.entities import OwnerNoteEntity
from src.modules.styles.domain.section_chunker import chunk_markdown_sections
from src.modules.styles.ports.output import (
    IEmbeddingService,
    IEmbeddingServiceDep,
    IOwnerNoteRepoDep,
    IOwnerNoteRepository,
    IVectorStore,
    IVectorStoreDep,
    VectorChunk,
)

MAX_NOTE_BYTES = 1_000_000  # 1 MB


class CreateOwnerNoteUsecase:
    def __init__(
        self,
        note_repo: IOwnerNoteRepoDep,
        vector_store: IVectorStoreDep,
        embedding_service: IEmbeddingServiceDep,
    ):
        self.note_repo: IOwnerNoteRepository = note_repo
        self.vector_store: IVectorStore = vector_store
        self.embedding_service: IEmbeddingService = embedding_service

    async def execute(
        self,
        title: str,
        content: str,
        citable_url: str | None = None,
        quality_score: float = 1.0,
    ) -> OwnerNoteEntity:
        if len(content.encode("utf-8")) > MAX_NOTE_BYTES:
            raise BadRequestException("Note content exceeds the 1 MB limit")

        note = OwnerNoteEntity(
            id=uuid.uuid4(),
            title=title.strip() or "Untitled Note",
            content=content,
            citable_url=citable_url.strip() if citable_url else None,
            quality_score=quality_score,
        )
        saved = self.note_repo.create(note)

        # Chunk and embed
        chunks = chunk_markdown_sections(saved.content, title=saved.title)
        if not chunks:
            # Fallback to single chunk
            from src.modules.styles.domain.section_chunker import MarkdownChunk

            chunks = [
                MarkdownChunk(
                    chunk_index=0,
                    heading_path=saved.title,
                    content=saved.content,
                    chunk_type="note",
                )
            ]

        texts_to_embed = [c.content for c in chunks]
        try:
            vectors = await self.embedding_service.embed_documents(texts_to_embed)
        except Exception:
            vectors = [[0.0] * self.embedding_service.dimension for _ in chunks]

        vector_chunks: list[VectorChunk] = []
        for i, chunk in enumerate(chunks):
            vec = vectors[i] if i < len(vectors) else None
            vector_chunks.append(
                VectorChunk(
                    id=uuid.uuid4(),
                    sample_id=None,
                    note_id=saved.id,
                    chunk_index=chunk.chunk_index,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    chunk_type="note",
                    embedding=vec,
                )
            )

        await self.vector_store.upsert_chunks(vector_chunks)
        return saved


class UpdateOwnerNoteUsecase:
    def __init__(
        self,
        note_repo: IOwnerNoteRepoDep,
        vector_store: IVectorStoreDep,
        embedding_service: IEmbeddingServiceDep,
    ):
        self.note_repo: IOwnerNoteRepository = note_repo
        self.vector_store: IVectorStore = vector_store
        self.embedding_service: IEmbeddingService = embedding_service

    async def execute(
        self,
        note_id: uuid.UUID,
        title: str,
        content: str,
        citable_url: str | None = None,
        quality_score: float = 1.0,
    ) -> OwnerNoteEntity:
        existing = self.note_repo.get(note_id)
        if not existing:
            raise NotFoundException(f"Owner note {note_id} not found")

        if len(content.encode("utf-8")) > MAX_NOTE_BYTES:
            raise BadRequestException("Note content exceeds the 1 MB limit")

        existing.title = title.strip() or existing.title
        existing.content = content
        existing.citable_url = citable_url.strip() if citable_url else None
        existing.quality_score = quality_score
        saved = self.note_repo.update(existing)

        # Delete previous chunks and re-embed
        await self.vector_store.delete_chunks_by_note_id(saved.id)

        chunks = chunk_markdown_sections(saved.content, title=saved.title)
        texts_to_embed = [c.content for c in chunks]
        try:
            vectors = await self.embedding_service.embed_documents(texts_to_embed)
        except Exception:
            vectors = [[0.0] * self.embedding_service.dimension for _ in chunks]

        vector_chunks: list[VectorChunk] = []
        for i, chunk in enumerate(chunks):
            vec = vectors[i] if i < len(vectors) else None
            vector_chunks.append(
                VectorChunk(
                    id=uuid.uuid4(),
                    sample_id=None,
                    note_id=saved.id,
                    chunk_index=chunk.chunk_index,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    chunk_type="note",
                    embedding=vec,
                )
            )

        await self.vector_store.upsert_chunks(vector_chunks)
        return saved


class ListOwnerNotesUsecase:
    def __init__(self, note_repo: IOwnerNoteRepoDep):
        self.note_repo: IOwnerNoteRepository = note_repo

    async def execute(self) -> list[OwnerNoteEntity]:
        return self.note_repo.list_all()


class GetOwnerNoteUsecase:
    def __init__(self, note_repo: IOwnerNoteRepoDep):
        self.note_repo: IOwnerNoteRepository = note_repo

    async def execute(self, note_id: uuid.UUID) -> OwnerNoteEntity:
        note = self.note_repo.get(note_id)
        if not note:
            raise NotFoundException(f"Owner note {note_id} not found")
        return note


class DeleteOwnerNoteUsecase:
    def __init__(self, note_repo: IOwnerNoteRepoDep, vector_store: IVectorStoreDep):
        self.note_repo: IOwnerNoteRepository = note_repo
        self.vector_store: IVectorStore = vector_store

    async def execute(self, note_id: uuid.UUID) -> bool:
        note = self.note_repo.get(note_id)
        if not note:
            raise NotFoundException(f"Owner note {note_id} not found")
        await self.vector_store.delete_chunks_by_note_id(note_id)
        return self.note_repo.delete(note_id)


CreateOwnerNoteUsecaseDep = Annotated[CreateOwnerNoteUsecase, Depends(CreateOwnerNoteUsecase)]
UpdateOwnerNoteUsecaseDep = Annotated[UpdateOwnerNoteUsecase, Depends(UpdateOwnerNoteUsecase)]
ListOwnerNotesUsecaseDep = Annotated[ListOwnerNotesUsecase, Depends(ListOwnerNotesUsecase)]
GetOwnerNoteUsecaseDep = Annotated[GetOwnerNoteUsecase, Depends(GetOwnerNoteUsecase)]
DeleteOwnerNoteUsecaseDep = Annotated[DeleteOwnerNoteUsecase, Depends(DeleteOwnerNoteUsecase)]
