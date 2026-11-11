"""Epic 12: diagrams for Dev.to are hosted on S3 under content-addressed keys with permanent public URLs."""

import hashlib
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from src.configs.config import Config
from src.modules.publishing.domain.devto_renderer import render_for_devto
from src.modules.publishing.infrastructure.adapters import asset_resolver
from src.modules.publishing.infrastructure.adapters.asset_resolver import resolve_asset
from src.modules.publishing.infrastructure.adapters.s3_asset_uploader import S3AssetUploader
from src.modules.publishing.ports.output.publisher import PublishError

PNG = b"\x89PNG\r\n\x1a\n" + b"diagram-bytes"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect width="1" height="1"/></svg>'


def make_config(**kw) -> Config:
    base = dict(_env_file=None, db_url="postgresql://u:p@localhost/db", s3_bucket="bucket-1",
                aws_access_key="AKIAEXAMPLE000000", aws_secret_key="secretsecretsecret")
    return Config(**{**base, **kw})


class FakeS3:
    def __init__(self, existing: set[str] | None = None, fail: bool = False):
        self.objects = {k: b"" for k in (existing or set())}
        self.puts: list[dict] = []
        self.fail = fail

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def put_object(self, **kw):
        if self.fail:
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
        self.puts.append(kw)
        self.objects[kw["Key"]] = kw["Body"]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_resolver.config, "data_dir", str(tmp_path))
    return tmp_path


def asset_files(data_dir, asset_id: str, png=True, svg=True):
    folder = data_dir / "assets" / "task-1"
    folder.mkdir(parents=True, exist_ok=True)
    if svg:
        (folder / f"{asset_id}.svg").write_bytes(SVG)
    if png:
        (folder / f"{asset_id}.png").write_bytes(PNG)
    return folder


async def test_uploads_png_with_content_addressed_key_and_public_url(data_dir):
    asset_files(data_dir, "abc")
    s3 = FakeS3()
    key, url = await S3AssetUploader(make_config(), client=s3).upload_asset("asset://abc")
    assert key == f"diagrams/{hashlib.sha256(PNG).hexdigest()[:24]}.png"
    assert url == f"https://bucket-1.s3.ap-southeast-1.amazonaws.com/{key}"
    put = s3.puts[0]
    assert put["ContentType"] == "image/png" and put["Body"] == PNG
    assert "immutable" in put["CacheControl"]


async def test_existing_object_is_not_uploaded_again(data_dir):
    asset_files(data_dir, "abc")
    key = f"diagrams/{hashlib.sha256(PNG).hexdigest()[:24]}.png"
    s3 = FakeS3(existing={key})
    got, _ = await S3AssetUploader(make_config(), client=s3).upload_asset("asset://abc")
    assert got == key and s3.puts == []


async def test_svg_only_assets_are_sanitized(data_dir):
    asset_files(data_dir, "only-svg", png=False)
    s3 = FakeS3()
    key, _ = await S3AssetUploader(make_config(), client=s3).upload_asset("asset://only-svg")
    assert key.endswith(".svg")
    assert s3.puts[0]["ContentType"] == "image/svg+xml" and b"<script" not in s3.puts[0]["Body"]


async def test_custom_prefix_and_public_base_url(data_dir):
    asset_files(data_dir, "abc")
    up = S3AssetUploader(make_config(s3_prefix="/img/", s3_public_base_url="https://cdn.example.com/"), client=FakeS3())
    key, url = await up.upload_asset("asset://abc")
    assert key.startswith("img/") and url == f"https://cdn.example.com/{key}"


async def test_s3_errors_become_publish_errors(data_dir):
    asset_files(data_dir, "abc")
    with pytest.raises(PublishError, match="S3 upload"):
        await S3AssetUploader(make_config(), client=FakeS3(fail=True)).upload_asset("asset://abc")


def test_missing_bucket_is_a_clear_error():
    with pytest.raises(PublishError, match="S3_BUCKET"):
        S3AssetUploader(make_config(s3_bucket=""))


async def test_resolver_prefers_the_png_recorded_on_the_diagram_asset(data_dir, monkeypatch):
    png = data_dir / "elsewhere.png"
    png.write_bytes(PNG)

    async def fake_asset(asset_id):
        return SimpleNamespace(png_path=str(png), svg_path=None)

    monkeypatch.setattr(asset_resolver, "_diagram_asset", fake_asset)
    data, name, mime = await resolve_asset("asset://xyz", prefer_raster=True)
    assert (data, name, mime) == (PNG, "elsewhere.png", "image/png")


async def test_resolver_default_keeps_sanity_behaviour(data_dir, monkeypatch):
    asset_files(data_dir, "abc", png=False)

    async def no_asset(asset_id):
        return None

    monkeypatch.setattr(asset_resolver, "_diagram_asset", no_asset)
    data, name, mime = await resolve_asset("asset://abc")
    assert name == "abc.svg" and mime == "image/svg+xml"


async def test_devto_render_uses_s3_png_and_picks_it_as_main_image(data_dir):
    asset_files(data_dir, "abc")
    revision = SimpleNamespace(
        markdown='# Title\n\nIntro.\n\n![Architecture](asset://abc "Architecture")\n',
        slug="title", tags=["aws"], metadata={}, title="Title", description="d",
    )
    up = S3AssetUploader(make_config(), client=FakeS3())
    result = await render_for_devto(revision=revision, canonical_url="https://site/posts/title", uploader=up)
    assert "asset://" not in result.body_markdown
    assert "https://bucket-1.s3.ap-southeast-1.amazonaws.com/diagrams/" in result.body_markdown
    assert result.main_image and result.main_image.endswith(".png")


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "s3"),
        ({"s3_bucket": ""}, "sanity"),
        ({"aws_secret_key": ""}, "sanity"),
        ({"image_host": "sanity"}, "sanity"),
    ],
)
def test_image_host_resolution(overrides, expected):
    assert make_config(**overrides).resolved_image_host == expected
