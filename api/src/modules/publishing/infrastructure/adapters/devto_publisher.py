import asyncio
from typing import Any, Callable
import uuid

import httpx

from src.configs import config
from src.configs.logger import get_logger
from src.libs.exceptions import BadRequestException, ErrorCode
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer
from src.modules.diagrams.ports.output.diagram_repository import IDiagramAssetRepository
from src.modules.publishing.domain.devto_renderer import render_for_devto
from src.modules.publishing.domain.sanity_renderer import IAssetUploader
from src.modules.publishing.ports.output.publisher import IPublisher, PublishError, PublishOutcome
from src.modules.shared.domain.entities import ArticleRevisionEntity, PublicationTarget

logger = get_logger(__name__)


class DevtoPublisher(IPublisher):
    """DEV Community / Forem HTTP API publisher with idempotency & rate-limiting (E8-S3)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        asset_uploader: IAssetUploader | None = None,
        diagram_renderer: IDiagramRenderer | None = None,
        diagram_repo: IDiagramAssetRepository | None = None,
    ):
        self._api_key = (
            api_key
            if api_key is not None
            else (config.dev_to_api_key.get_secret_value() if config.dev_to_api_key else None)
        )
        self.base_url = (base_url or config.dev_to_base_url).rstrip("/")
        self._client = http_client
        self._asset_uploader = asset_uploader
        self._diagram_renderer = diagram_renderer
        self._diagram_repo = diagram_repo

    @property
    def destination(self) -> PublicationTarget:
        return PublicationTarget.DEVTO

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise BadRequestException("DEV_TO_API_KEY is not configured", code=ErrorCode.BAD_REQUEST)
        # Note: API key is NEVER logged or traced
        return {
            "api-key": self._api_key,
            "Accept": "application/vnd.forem.api-v1+json",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=30.0)

    async def _send_with_retry(self, request_fn: Callable[[], Any], operation: str) -> httpx.Response:
        """Bounded retries: up to 3 attempts with Retry-After or exponential backoff for 429 and 5xx; 4xx validation errors fail immediately."""
        max_attempts = 3
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp: httpx.Response = await request_fn()

                # Status 429 Too Many Requests -> retryable with Retry-After delay
                if resp.status_code == 429:
                    retry_after_str = resp.headers.get("retry-after")
                    try:
                        delay = float(retry_after_str) if retry_after_str else 0.5 * (2 ** (attempt - 1))
                    except ValueError:
                        delay = 0.5 * (2 ** (attempt - 1))

                    delay = min(delay, 10.0)
                    if attempt == max_attempts:
                        logger.error(f"{operation} rate limited (429) after {attempt} attempts")
                        raise PublishError(f"{operation} rate limited (429): {resp.text[:300]}", retryable=True, status_code=429)

                    logger.warning(f"{operation} 429 rate limit hit, backing off {delay}s (attempt {attempt}/{max_attempts})")
                    await asyncio.sleep(delay)
                    continue

                # Client errors (4xx other than 429) fail immediately without retry
                if 400 <= resp.status_code < 500:
                    err_body = resp.text[:400]
                    logger.error(f"{operation} failed with client error: {resp.status_code} {err_body}")
                    raise PublishError(
                        f"{operation} validation error ({resp.status_code}): {err_body}",
                        retryable=False,
                        status_code=resp.status_code,
                    )

                resp.raise_for_status()
                return resp

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == max_attempts:
                    logger.error(f"{operation} timed out or network error after {attempt} attempts: {exc}")
                    raise PublishError(f"{operation} network error: {exc}", retryable=True)
                delay = 0.5 * (2 ** (attempt - 1))
                logger.warning(f"{operation} attempt {attempt}/{max_attempts} failed ({exc}), retrying in {delay}s...")
                await asyncio.sleep(delay)

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (500, 502, 503, 504) and attempt < max_attempts:
                    delay = 0.5 * (2 ** (attempt - 1))
                    logger.warning(f"{operation} 5xx server error {exc.response.status_code}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"{operation} HTTP error {exc.response.status_code}: {exc.response.text[:400]}")
                raise PublishError(f"{operation} failed ({exc.response.status_code})", retryable=False, status_code=exc.response.status_code)

        raise PublishError(f"{operation} failed after {max_attempts} attempts: {last_exc}", retryable=True)

    async def _find_existing_article(
        self, client: httpx.AsyncClient, canonical_url: str | None, title: str
    ) -> dict[str, Any] | None:
        """Search owner's articles (/api/articles/me/all) for matching canonical_url or exact title for idempotency."""
        try:
            page = 1
            while True:
                resp = await self._send_with_retry(
                    lambda: client.get(
                        f"{self.base_url}/articles/me/all?page={page}&per_page=100",
                        headers=self._headers(),
                    ),
                    operation="List owner articles",
                )
                articles = resp.json()
                if not isinstance(articles, list) or len(articles) == 0:
                    break

                for a in articles:
                    a_canon = a.get("canonical_url")
                    a_title = (a.get("title") or "").strip()
                    if canonical_url and a_canon and a_canon.rstrip("/") == canonical_url.rstrip("/"):
                        return a
                    if a_title and a_title.lower() == title.strip().lower():
                        return a

                if len(articles) < 100 or page >= 5:
                    break
                page += 1

            return None
        except Exception as exc:
            logger.warning(f"Failed to query existing articles from Dev.to: {exc}")
            return None

    async def publish(
        self,
        task_id: uuid.UUID,
        revision: ArticleRevisionEntity,
        existing_remote_id: str | None = None,
        on_asset_uploaded: Callable[[str, str, str], None] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PublishOutcome:
        """Publishes or updates article on Dev.to with idempotency and mode check."""
        client = await self._get_client()
        try:
            # Mode determination (E8-S4)
            opts = options or {}
            mode = opts.get("mode") or opts.get("devto_mode") or "draft"
            is_published = (mode == "published")

            # Query diagram assets if not explicitly passed
            diagram_assets = opts.get("diagram_assets")
            if diagram_assets is None and self._diagram_repo is not None:
                try:
                    diagram_assets = self._diagram_repo.list_by_revision(revision.id) or self._diagram_repo.list_by_task(task_id)
                except Exception as exc:
                    logger.warning(f"Could not load diagram assets: {exc}")

            # Deterministic render transform
            canonical_url = f"{config.sanity_site_base_url.rstrip('/')}/posts/{revision.slug}"
            render_res = await render_for_devto(
                revision=revision,
                canonical_url=canonical_url,
                uploader=self._asset_uploader,
                diagram_renderer=self._diagram_renderer,
                diagram_assets=diagram_assets,
                on_asset_uploaded=on_asset_uploaded,
            )

            target_id = existing_remote_id

            # First publish idempotency check:
            # If no stored remote id, list articles to see if a prior attempt succeeded
            if not target_id:
                matched = await self._find_existing_article(client, canonical_url, render_res.title)
                if matched and matched.get("id"):
                    target_id = str(matched["id"])
                    logger.info(f"Adopting existing Dev.to article id {target_id} matching title/canonical_url")

            article_payload: dict[str, Any] = {
                "title": render_res.title,
                "body_markdown": render_res.body_markdown,
                "published": is_published,
                "tags": render_res.tags,
                "canonical_url": render_res.canonical_url,
            }
            if render_res.main_image:
                article_payload["main_image"] = render_res.main_image
            if render_res.description:
                article_payload["description"] = render_res.description

            request_body = {"article": article_payload}

            if target_id:
                # Update existing article via PUT
                put_url = f"{self.base_url}/articles/{target_id}"
                resp = await self._send_with_retry(
                    lambda: client.put(put_url, headers=self._headers(), json=request_body),
                    operation=f"Update Dev.to article {target_id}",
                )
                data = resp.json()
            else:
                # Create new article via POST
                post_url = f"{self.base_url}/articles"
                resp = await self._send_with_retry(
                    lambda: client.post(post_url, headers=self._headers(), json=request_body),
                    operation="Create Dev.to article",
                )
                data = resp.json()
                target_id = str(data.get("id"))

            remote_url = data.get("url") or f"https://dev.to/dashboard"
            studio_url = f"https://dev.to/dashboard"

            return PublishOutcome(
                destination=PublicationTarget.DEVTO,
                remote_document_id=target_id,
                remote_url=remote_url,
                rendered_content_hash=render_res.rendered_content_hash,
                studio_url=studio_url,
                rendered_markdown=render_res.body_markdown,
            )

        finally:
            if self._client is None:
                await client.aclose()

    async def unpublish(self, remote_document_id: str) -> None:
        """Unpublish/archive article on Dev.to."""
        client = await self._get_client()
        try:
            # 1. Try unpublish endpoint
            try:
                await self._send_with_retry(
                    lambda: client.put(
                        f"{self.base_url}/articles/{remote_document_id}/unpublish",
                        headers=self._headers(),
                    ),
                    operation=f"Unpublish Dev.to article {remote_document_id}",
                )
                return
            except Exception:
                pass

            # 2. Fallback: update article to published=False
            await self._send_with_retry(
                lambda: client.put(
                    f"{self.base_url}/articles/{remote_document_id}",
                    headers=self._headers(),
                    json={"article": {"published": False}},
                ),
                operation=f"Set published=False on Dev.to article {remote_document_id}",
            )
        finally:
            if self._client is None:
                await client.aclose()
