"""pgvector adapter using SQLModel and SQLAlchemy pgvector Vector type.

Architecture decision (E6-S1):
We chose SQLModel with the `pgvector` SQLAlchemy type (`Vector`) rather than `langchain-postgres` `PGVector` because:
1. It aligns directly with the application's single-database clean architecture and SQLModel session management,
   avoiding an extra third-party persistence layer and separate table lifecycle.
2. It allows native SQL JOINs between `sample_chunks` and `writing_samples` / `owner_notes` in a single query
   to filter by `approved_as_style_example`, check origins, and retrieve titles without duplicate metadata tables.
3. It keeps transactional consistency with Alembic migrations and application entities.
"""

from typing import Annotated
import uuid

from fastapi import Depends
from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep, db_session_manager
from src.modules.shared.infrastructure.models import OwnerNoteModel, SampleChunkModel, WritingSampleModel
from src.modules.styles.ports.output.vector_store import IVectorStore, VectorChunk, VectorSearchResult


class PgVectorStore(IVectorStore):
    """SQLModel + pgvector implementation of IVectorStore."""

    def __init__(self, session: SessionDep | None = None):
        self._session = session

    def _get_session(self) -> Session:
        if self._session is not None:
            return self._session
        return Session(db_session_manager.engine)

    async def upsert_chunks(self, chunks: list[VectorChunk]) -> None:
        if not chunks:
            return
        session = self._get_session()
        try:
            for c in chunks:
                model = SampleChunkModel(
                    id=c.id,
                    sample_id=c.sample_id,
                    note_id=c.note_id,
                    chunk_index=c.chunk_index,
                    heading_path=c.heading_path,
                    content=c.content,
                    chunk_type=c.chunk_type,
                    embedding=c.embedding,
                )
                session.add(model)
            session.commit()
        finally:
            if self._session is None:
                session.close()

    async def delete_chunks_by_sample_id(self, sample_id: uuid.UUID) -> None:
        session = self._get_session()
        try:
            stmt = delete(SampleChunkModel).where(SampleChunkModel.sample_id == sample_id)
            session.exec(stmt)
            session.commit()
        finally:
            if self._session is None:
                session.close()

    async def delete_chunks_by_note_id(self, note_id: uuid.UUID) -> None:
        session = self._get_session()
        try:
            stmt = delete(SampleChunkModel).where(SampleChunkModel.note_id == note_id)
            session.exec(stmt)
            session.commit()
        finally:
            if self._session is None:
                session.close()

    async def get_chunks_by_ids(self, chunk_ids: list[uuid.UUID]) -> list[VectorChunk]:
        if not chunk_ids:
            return []
        session = self._get_session()
        try:
            stmt = select(SampleChunkModel).where(col(SampleChunkModel.id).in_(chunk_ids))
            models = session.exec(stmt).all()
            return [
                VectorChunk(
                    id=m.id,
                    sample_id=m.sample_id,
                    note_id=m.note_id,
                    chunk_index=m.chunk_index,
                    heading_path=m.heading_path,
                    content=m.content,
                    chunk_type=m.chunk_type,
                    embedding=None,
                )
                for m in models
            ]
        finally:
            if self._session is None:
                session.close()

    async def similarity_search(
        self,
        query_embedding: list[float],
        k: int = 5,
        chunk_type: str | None = None,
        sample_approved_only: bool = True,
        origin: str | None = None,
        exclude_sample_id: uuid.UUID | None = None,
    ) -> list[VectorSearchResult]:
        session = self._get_session()
        try:
            # Query sample chunks ordering by cosine distance
            cosine_dist = SampleChunkModel.embedding.cosine_distance(query_embedding)
            stmt = (
                select(
                    SampleChunkModel,
                    cosine_dist.label("distance"),
                    func.coalesce(WritingSampleModel.title, OwnerNoteModel.title).label("sample_title"),
                    WritingSampleModel.origin.label("sample_origin"),
                    WritingSampleModel.remote_id.label("remote_id"),
                    OwnerNoteModel.citable_url.label("citable_url"),
                    OwnerNoteModel.quality_score.label("quality_score"),
                )
                .outerjoin(WritingSampleModel, SampleChunkModel.sample_id == WritingSampleModel.id)
                .outerjoin(OwnerNoteModel, SampleChunkModel.note_id == OwnerNoteModel.id)
                .where(SampleChunkModel.embedding.is_not(None))
            )

            if chunk_type is not None:
                stmt = stmt.where(SampleChunkModel.chunk_type == chunk_type)

            if exclude_sample_id is not None:
                stmt = stmt.where(
                    (SampleChunkModel.sample_id != exclude_sample_id) | (SampleChunkModel.sample_id.is_(None))
                )

            if sample_approved_only:
                # If chunk is from a sample, it must be approved. If from note, allow it.
                stmt = stmt.where(
                    (WritingSampleModel.approved_as_style_example.is_(True))
                    | (SampleChunkModel.sample_id.is_(None))
                )

            if origin is not None:
                if origin == "owner_note":
                    stmt = stmt.where(SampleChunkModel.note_id.is_not(None))
                else:
                    stmt = stmt.where(WritingSampleModel.origin == origin)

            stmt = stmt.order_by(cosine_dist).limit(k)
            rows = session.exec(stmt).all()

            results: list[VectorSearchResult] = []
            for row in rows:
                chunk_model = row[0]
                distance = float(row[1]) if row[1] is not None else 1.0
                title = row[2]
                row_origin = row[3] or ("owner_note" if chunk_model.note_id else "unknown")
                remote_id = row[4]
                citable_url = row[5]
                quality_score = float(row[6]) if row[6] is not None else None
                similarity = max(0.0, 1.0 - distance)

                chunk = VectorChunk(
                    id=chunk_model.id,
                    sample_id=chunk_model.sample_id,
                    note_id=chunk_model.note_id,
                    chunk_index=chunk_model.chunk_index,
                    heading_path=chunk_model.heading_path,
                    content=chunk_model.content,
                    chunk_type=chunk_model.chunk_type,
                    embedding=None,  # Omit large embedding payload in search results
                )
                results.append(
                    VectorSearchResult(
                        chunk=chunk,
                        similarity=similarity,
                        sample_title=title,
                        origin=row_origin,
                        remote_id=remote_id,
                        citable_url=citable_url,
                        quality_score=quality_score,
                    )
                )

            return results
        finally:
            if self._session is None:
                session.close()


def get_vector_store(session: SessionDep) -> IVectorStore:
    return PgVectorStore(session=session)


IVectorStoreDep = Annotated[IVectorStore, Depends(get_vector_store)]
