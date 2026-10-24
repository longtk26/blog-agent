from .embedding_service import IEmbeddingService
from .owner_note_repository import IOwnerNoteRepository
from .style_guide_repository import IStyleGuideRepository
from .style_profile_repository import IStyleProfileRepository
from .vector_store import IVectorStore, VectorChunk, VectorSearchResult
from .writing_sample_repository import IWritingSampleRepository

_DEPS = {
    "IStyleGuideRepoDep",
    "IWritingSampleRepoDep",
    "IStyleProfileRepoDep",
    "IOwnerNoteRepoDep",
    "IVectorStoreDep",
    "IEmbeddingServiceDep",
}


def __getattr__(name: str):
    if name in _DEPS:
        from src.modules.styles.infrastructure import adapters, persistence

        if hasattr(adapters, name):
            return getattr(adapters, name)
        if hasattr(persistence, name):
            return getattr(persistence, name)
    raise AttributeError(name)


__all__ = [
    "IStyleGuideRepository",
    "IStyleGuideRepoDep",
    "IWritingSampleRepository",
    "IWritingSampleRepoDep",
    "IStyleProfileRepository",
    "IStyleProfileRepoDep",
    "IOwnerNoteRepository",
    "IOwnerNoteRepoDep",
    "IVectorStore",
    "IVectorStoreDep",
    "VectorChunk",
    "VectorSearchResult",
    "IEmbeddingService",
    "IEmbeddingServiceDep",
]
