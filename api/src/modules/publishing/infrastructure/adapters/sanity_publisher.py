import asyncio
import hashlib
import re
from typing import Any, Callable
import uuid

import httpx

from src.configs import config
from src.configs.logger import get_logger
from src.libs.exceptions import BadRequestException, ConflictException, ErrorCode
from src.modules.publishing.domain import render_for_sanity, sanitize_svg, validate_sanity_slug
from src.modules.publishing.domain.sanity_renderer import IAssetUploader
from src.modules.publishing.infrastructure.adapters.asset_resolver import resolve_asset
from src.modules.publishing.ports.output.publisher import IPublisher, PublishError, PublishOutcome
from src.modules.publishing.ports.output.thumbnail_generator import IThumbnailGenerator
from src.modules.shared.domain.entities import ArticleRevisionEntity, PublicationTarget
from src.modules.shared.infrastructure.models._columns import utcnow

logger = get_logger(__name__)


class SanityPublisher(IPublisher, IAssetUploader):
    """Sanity HTTP API publisher (E5-S3)."""

    def __init__(
        self,
        project_id: str | None = None,
        dataset: str | None = None,
        api_version: str | None = None,
        token: str | None = None,
        site_base_url: str | None = None,
        studio_base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        thumbnail_generator: IThumbnailGenerator | None = None,
    ):
        self.project_id = project_id or config.sanity_project_id
        # Allow test dataset override if set
        self.dataset = (
            config.sanity_test_dataset
            if config.sanity_test_dataset and not dataset
            else (dataset or config.sanity_dataset)
        )
        self.api_version = api_version or config.sanity_api_version
        self._token = (
            token
            if token is not None
            else (config.sanity_api_write_token.get_secret_value() if config.sanity_api_write_token else None)
        )
        self.site_base_url = (site_base_url or config.sanity_site_base_url).rstrip("/")
        self.studio_base_url = (studio_base_url or config.sanity_studio_base_url).rstrip("/")
        self._client = http_client
        self._thumbnail_generator = thumbnail_generator

    @property
    def destination(self) -> PublicationTarget:
        return PublicationTarget.SANITY

    @property
    def base_url(self) -> str:
        return f"https://{self.project_id}.api.sanity.io/v{self.api_version}"

    @property
    def mutate_url(self) -> str:
        return f"{self.base_url}/data/mutate/{self.dataset}?returnIds=true&visibility=sync"

    @property
    def asset_upload_url(self) -> str:
        return f"{self.base_url}/assets/images/{self.dataset}"

    def doc_url(self, doc_id: str) -> str:
        return f"{self.base_url}/data/doc/{self.dataset}/{doc_id}"

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        if not self._token:
            raise BadRequestException("SANITY_API_WRITE_TOKEN is not configured", code=ErrorCode.BAD_REQUEST)
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": content_type,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=30.0)

    @staticmethod
    def _extract_doc(data: Any) -> dict[str, Any] | None:
        if isinstance(data, dict):
            docs = data.get("documents")
            if isinstance(docs, list):
                return docs[0] if len(docs) > 0 and isinstance(docs[0], dict) else None
            return data
        return None

    async def check_collision(self, doc_id: str) -> bool:
        """Returns True if a document with doc_id already exists in Sanity."""
        client = await self._get_client()
        try:
            resp = await client.get(self.doc_url(doc_id), headers=self._headers())
            if resp.status_code == 200:
                data = resp.json()
                doc = self._extract_doc(data)
                return bool(doc and doc.get("_id"))
            return False
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return False
            raise
        finally:
            if self._client is None:
                await client.aclose()

    async def _upload_raw_asset(self, raw_bytes: bytes, filename: str, content_type: str) -> tuple[str, str]:
        """Upload raw image bytes to Sanity assets API."""
        client = await self._get_client()
        try:
            url = f"{self.asset_upload_url}?filename={filename}"
            headers = self._headers(content_type=content_type)

            resp = await self._send_with_retry(
                lambda: client.post(url, headers=headers, content=raw_bytes),
                operation=f"Upload asset {filename}",
            )
            data = resp.json()
            doc = data.get("document", {}) if "document" in data else data
            asset_id = doc.get("_id")
            cdn_url = doc.get("url")
            if not asset_id or not cdn_url:
                raise PublishError(f"Sanity asset upload returned unexpected response: {data}")
            return asset_id, cdn_url
        finally:
            if self._client is None:
                await client.aclose()

    async def upload_asset(self, src: str, alt: str = "", title: str = "") -> tuple[str, str]:
        """Upload local or asset:// image to Sanity assets API."""
        # 1. Resolve asset data and filename
        raw_bytes, filename, content_type = await self._resolve_asset(src)

        # 2. Sanitize SVG if applicable
        if content_type == "image/svg+xml" or filename.lower().endswith(".svg"):
            raw_bytes = sanitize_svg(raw_bytes)
            content_type = "image/svg+xml"

        # 3. Upload to Sanity assets endpoint
        return await self._upload_raw_asset(raw_bytes, filename, content_type)

    async def _resolve_asset(self, src: str) -> tuple[bytes, str, str]:
        return await resolve_asset(src)

    async def publish(
        self,
        task_id: uuid.UUID,
        revision: ArticleRevisionEntity,
        existing_remote_id: str | None = None,
        on_asset_uploaded: Callable[[str, str, str], None] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PublishOutcome:
        # Determine deterministic document _id: existing or validated slug
        if existing_remote_id:
            doc_id = existing_remote_id
        else:
            doc_id = validate_sanity_slug(revision.slug)
            # Collision check on first publish
            taken = await self.check_collision(doc_id)
            if taken:
                raise ConflictException(
                    f"The slug '{doc_id}' is already taken in Sanity. Please choose a different slug.",
                    code=ErrorCode.SLUG_TAKEN,
                )

        # Render markdown and upload assets
        render_res = await render_for_sanity(revision, uploader=self, on_asset_uploaded=on_asset_uploaded)

        cover_image_ref = render_res.cover_image_asset_ref
        if not cover_image_ref and config.sanity_generate_thumbnail and self._thumbnail_generator is not None:
            try:
                # Extract TOC headings from metadata outline or markdown
                headings: list[str] = []
                if revision.metadata and "outline" in revision.metadata:
                    outline_data = revision.metadata["outline"]
                    if isinstance(outline_data, dict):
                        sections = outline_data.get("sections", [])
                        headings = [
                            s.get("heading")
                            for s in sections
                            if isinstance(s, dict) and s.get("heading")
                        ]
                if not headings:
                    headings = [h.strip() for h in re.findall(r"^##\s+(.+)$", revision.markdown, re.MULTILINE)]

                thumb = await self._thumbnail_generator.generate_thumbnail(
                    title=revision.title,
                    description=revision.description,
                    table_of_contents=headings,
                    slug=doc_id,
                )
                if thumb is not None:
                    raw_bytes, filename, content_type = thumb
                    asset_id, cdn_url = await self._upload_raw_asset(raw_bytes, filename, content_type)
                    if asset_id:
                        cover_image_ref = asset_id
                        logger.info(f"Generated and attached thumbnail {asset_id} to post {doc_id}")
                        if on_asset_uploaded:
                            on_asset_uploaded("thumbnail://generated", asset_id, cdn_url)
            except Exception as thumb_err:
                logger.warning(f"Thumbnail generation skipped due to error: {thumb_err}")

        now_iso = utcnow().isoformat()

        # Build stable tags array
        tags_payload = [
            {
                "_key": f"tag_{hashlib.sha256(t.strip().encode('utf-8')).hexdigest()[:8]}",
                "_type": "tag",
                "value": t.strip(),
            }
            for t in revision.tags
        ]

        patch_set: dict[str, Any] = {
            "title": revision.title,
            "description": revision.description,
            "content": render_res.rendered_markdown,
            "tags": tags_payload,
            "updatedAt": now_iso,
            "images": render_res.images,
        }
        if cover_image_ref:
            patch_set["image"] = {
                "_type": "image",
                "asset": {
                    "_type": "reference",
                    "_ref": cover_image_ref,
                },
            }

        mutations = [
            {
                "createIfNotExists": {
                    "_id": doc_id,
                    "_type": "post",
                }
            },
            {
                "patch": {
                    "id": doc_id,
                    "set": patch_set,
                    "setIfMissing": {
                        "publishedAt": now_iso,
                    },
                }
            },
        ]

        client = await self._get_client()
        try:
            # Send mutation transaction with bounded retry
            await self._send_with_retry(
                lambda: client.post(self.mutate_url, headers=self._headers(), json={"mutations": mutations}),
                operation=f"Mutate post {doc_id}",
            )

            # Read back document to confirm content hash matches
            get_resp = await self._send_with_retry(
                lambda: client.get(self.doc_url(doc_id), headers=self._headers()),
                operation=f"Readback post {doc_id}",
            )
            data = get_resp.json()
            remote_doc = self._extract_doc(data) or {}
            remote_content = remote_doc.get("content", "")
            remote_hash = hashlib.sha256(remote_content.encode("utf-8")).hexdigest()

            if remote_hash != render_res.rendered_content_hash:
                raise PublishError(
                    f"Readback content hash mismatch: expected {render_res.rendered_content_hash[:12]}, got {remote_hash[:12]}"
                )

            remote_url = f"{self.site_base_url}/posts/{doc_id}"
            studio_url = f"{self.studio_base_url}/structure/post;{doc_id}"

            return PublishOutcome(
                destination=PublicationTarget.SANITY,
                remote_document_id=doc_id,
                remote_url=remote_url,
                rendered_content_hash=render_res.rendered_content_hash,
                studio_url=studio_url,
                rendered_markdown=render_res.rendered_markdown,
            )
        finally:
            if self._client is None:
                await client.aclose()

    async def unpublish(self, remote_document_id: str) -> None:
        """Delete post (and draft if present) from Sanity."""
        mutations = [
            {"delete": {"id": remote_document_id}},
            {"delete": {"id": f"drafts.{remote_document_id}"}},
        ]
        client = await self._get_client()
        try:
            await self._send_with_retry(
                lambda: client.post(self.mutate_url, headers=self._headers(), json={"mutations": mutations}),
                operation=f"Delete post {remote_document_id}",
            )
        finally:
            if self._client is None:
                await client.aclose()

    async def _send_with_retry(self, request_fn: Callable[[], Any], operation: str) -> httpx.Response:
        """Bounded retries: 3 attempts with exponential backoff for 5xx/network errors; 4xx fail immediately."""
        max_attempts = 3
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp: httpx.Response = await request_fn()
                if 400 <= resp.status_code < 500:
                    # Non-retryable client error
                    text = resp.text[:500]
                    logger.error(f"{operation} failed with 4xx: {resp.status_code} {text}")
                    raise PublishError(f"{operation} failed ({resp.status_code}): {text}", retryable=False, status_code=resp.status_code)
                resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == max_attempts:
                    logger.error(f"{operation} timed out or network error after {attempt} attempts: {exc}")
                    raise PublishError(f"{operation} network error: {exc}", retryable=True)
                delay = 0.5 * (2 ** (attempt - 1))
                logger.warning(f"{operation} failed attempt {attempt}/{max_attempts}, retrying in {delay}s...")
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (500, 502, 503, 504) and attempt < max_attempts:
                    delay = 0.5 * (2 ** (attempt - 1))
                    logger.warning(f"{operation} 5xx error {exc.response.status_code}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"{operation} HTTP error {exc.response.status_code}: {exc.response.text[:500]}")
                raise PublishError(f"{operation} failed ({exc.response.status_code})", retryable=False, status_code=exc.response.status_code)

        raise PublishError(f"{operation} failed after {max_attempts} attempts: {last_exc}", retryable=True)
