from dataclasses import dataclass
import hashlib
import logging
from typing import Annotated
import uuid

from fastapi import Depends
import httpx

from src.configs.config import config
from src.modules.shared.domain.entities import WritingSampleEntity
from src.modules.styles.domain.sample_importers import (
    RawSampleItem,
    fetch_local_samples,
    fetch_sanity_samples,
)
from src.modules.styles.domain.section_chunker import chunk_markdown_sections
from src.modules.styles.ports.output import (
    IEmbeddingService,
    IEmbeddingServiceDep,
    IVectorStore,
    IVectorStoreDep,
    IWritingSampleRepoDep,
    IWritingSampleRepository,
    VectorChunk,
)

logger = logging.getLogger(__name__)


@dataclass
class ImportSamplesResult:
    imported: int
    updated: int
    skipped: int
    total_chunks: int


class ImportSamplesUsecase:
    def __init__(
        self,
        sample_repo: IWritingSampleRepoDep,
        vector_store: IVectorStoreDep,
        embedding_service: IEmbeddingServiceDep,
    ):
        self.sample_repo: IWritingSampleRepository = sample_repo
        self.vector_store: IVectorStore = vector_store
        self.embedding_service: IEmbeddingService = embedding_service

    async def execute(
        self,
        sources: list[str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> ImportSamplesResult:
        sources = sources or ["sanity", "local"]
        raw_items: list[RawSampleItem] = []

        # 1. Fetch from requested sources
        if "sanity" in sources and config.sanity_project_id:
            token = config.sanity_api_write_token.get_secret_value() if config.sanity_api_write_token else None
            sanity_items = await fetch_sanity_samples(
                project_id=config.sanity_project_id,
                dataset=config.sanity_dataset,
                api_version=config.sanity_api_version,
                token=token,
                client=http_client,
            )
            raw_items.extend(sanity_items)

        if "local" in sources:
            local_items = fetch_local_samples(config.blogs_dir)
            raw_items.extend(local_items)

        # 2. De-duplicate raw items
        canonical_items: list[RawSampleItem] = []
        seen_hashes: set[str] = set()
        seen_sanity_ids: set[str] = set()

        for item in raw_items:
            content_hash = hashlib.sha256(item.content.encode("utf-8")).hexdigest()
            # If item maps to a sanity ID we already imported, skip duplicate
            if item.meta_sanity_id and item.meta_sanity_id in seen_sanity_ids:
                continue
            if content_hash in seen_hashes:
                continue

            if item.meta_sanity_id:
                seen_sanity_ids.add(item.meta_sanity_id)
            seen_hashes.add(content_hash)
            canonical_items.append(item)

        imported = 0
        updated = 0
        skipped = 0
        total_chunks = 0

        # 3. Process canonical items
        for raw in canonical_items:
            content_hash = hashlib.sha256(raw.content.encode("utf-8")).hexdigest()
            existing = self.sample_repo.get_by_origin_and_remote(raw.origin, raw.remote_id)

            if existing is not None:
                if existing.content_hash == content_hash:
                    # Content is unchanged, skip re-embedding
                    skipped += 1
                    continue

                # Content updated: update sample record and re-embed chunks
                existing.title = raw.title
                existing.tags = raw.tags
                existing.published_at = raw.published_at or existing.published_at
                existing.content = raw.content
                existing.content_hash = content_hash
                saved_sample = self.sample_repo.update(existing)

                # Delete old chunks
                await self.vector_store.delete_chunks_by_sample_id(saved_sample.id)
                updated += 1
            else:
                # New sample
                new_sample = WritingSampleEntity(
                    id=uuid.uuid4(),
                    origin=raw.origin,
                    remote_id=raw.remote_id,
                    title=raw.title,
                    tags=raw.tags,
                    published_at=raw.published_at,
                    approved_as_style_example=True,
                    content=raw.content,
                    content_hash=content_hash,
                )
                saved_sample = self.sample_repo.create(new_sample)
                imported += 1

            # Chunk and embed
            chunks = chunk_markdown_sections(saved_sample.content, title=saved_sample.title)
            if not chunks:
                continue

            texts_to_embed = [c.content for c in chunks]
            try:
                vectors = await self.embedding_service.embed_documents(texts_to_embed)
            except Exception as e:
                logger.warning(f"Failed to embed chunks for '{saved_sample.title}': {e}")
                vectors = [[0.0] * self.embedding_service.dimension for _ in chunks]

            vector_chunks: list[VectorChunk] = []
            for i, chunk in enumerate(chunks):
                vec = vectors[i] if i < len(vectors) else None
                vector_chunks.append(
                    VectorChunk(
                        id=uuid.uuid4(),
                        sample_id=saved_sample.id,
                        note_id=None,
                        chunk_index=chunk.chunk_index,
                        heading_path=chunk.heading_path,
                        content=chunk.content,
                        chunk_type=chunk.chunk_type,
                        embedding=vec,
                    )
                )

            await self.vector_store.upsert_chunks(vector_chunks)
            total_chunks += len(vector_chunks)

        logger.info(
            f"Imported {imported} samples, updated {updated}, skipped {skipped}, created {total_chunks} chunks"
        )
        return ImportSamplesResult(
            imported=imported,
            updated=updated,
            skipped=skipped,
            total_chunks=total_chunks,
        )


ImportSamplesUsecaseDep = Annotated[ImportSamplesUsecase, Depends(ImportSamplesUsecase)]
