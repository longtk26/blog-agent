"""Hosts article images (diagrams first) on S3 with permanent public URLs (Epic 12).

S3 caps presigned URLs at 7 days (verified 2026-11-11: ``X-Amz-Expires must be less than 604800 seconds``),
so published images use plain object URLs instead. The bucket allows anonymous ``s3:GetObject`` on the
``S3_PREFIX`` folder only (see ``scripts/setup_s3_public_prefix.py``); everything else stays private.

Keys are content-addressed (``<prefix><sha256[:24]>.<ext>``): re-publishing the same diagram reuses the same
object and URL, and an edited diagram gets a new URL, so CDNs and Dev.to's image cache never serve stale bytes.
"""

import asyncio
import hashlib
import mimetypes
from functools import cached_property

from src.configs import config as app_config
from src.configs.config import Config
from src.configs.logger import get_logger
from src.modules.publishing.domain import sanitize_svg
from src.modules.publishing.infrastructure.adapters.asset_resolver import resolve_asset
from src.modules.publishing.ports.output.publisher import PublishError

logger = get_logger(__name__)

_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif", "image/svg+xml": "svg"}


class S3AssetUploader:
    """``IAssetUploader`` for S3. Returns ``(object key, public URL)``."""

    def __init__(self, config: Config | None = None, client=None):
        self.config = config or app_config
        if not self.config.s3_bucket:
            raise PublishError("S3_BUCKET is not configured")
        self.bucket = self.config.s3_bucket
        self.prefix = self.config.s3_prefix.strip("/") + "/" if self.config.s3_prefix.strip("/") else ""
        self._client = client

    @cached_property
    def client(self):
        if self._client is not None:
            return self._client
        import boto3

        return boto3.client(
            "s3",
            region_name=self.config.s3_region,
            aws_access_key_id=self.config.aws_access_key.get_secret_value() if self.config.aws_access_key else None,
            aws_secret_access_key=self.config.aws_secret_key.get_secret_value() if self.config.aws_secret_key else None,
        )

    def public_url(self, key: str) -> str:
        base = (self.config.s3_public_base_url or "").rstrip("/")
        if not base:
            base = f"https://{self.bucket}.s3.{self.config.s3_region}.amazonaws.com"
        return f"{base}/{key}"

    def key_for(self, data: bytes, mime: str, filename: str = "") -> str:
        ext = _EXT.get(mime) or (mimetypes.guess_extension(mime) or "").lstrip(".") or filename.rsplit(".", 1)[-1]
        return f"{self.prefix}{hashlib.sha256(data).hexdigest()[:24]}.{ext or 'bin'}"

    def _put_if_missing(self, key: str, data: bytes, mime: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return False
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
                raise
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=mime,
            CacheControl="public, max-age=31536000, immutable",
        )
        return True

    async def upload_bytes(self, data: bytes, mime: str, filename: str = "") -> tuple[str, str]:
        if mime == "image/svg+xml":
            data = sanitize_svg(data)
        key = self.key_for(data, mime, filename)
        try:
            created = await asyncio.to_thread(self._put_if_missing, key, data, mime)
        except Exception as exc:
            raise PublishError(f"S3 upload of {filename or key} failed: {exc}") from exc
        logger.info("S3 asset ready", extra={"context": {"key": key, "uploaded": created, "bytes": len(data)}})
        return key, self.public_url(key)

    async def upload_asset(self, src: str, alt: str = "", title: str = "") -> tuple[str, str]:
        data, filename, mime = await resolve_asset(src, prefer_raster=True)
        if filename.lower().endswith(".svg"):
            mime = "image/svg+xml"
        return await self.upload_bytes(data, mime, filename)
