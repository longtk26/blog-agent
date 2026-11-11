"""Epic 14: diagrams must stay readable in DEV's 800px image column."""

import struct
import zlib
from types import SimpleNamespace

from src.modules.diagrams.domain.readability import column_width_finding, max_drawn_width, png_size
from src.modules.publishing.domain.devto_renderer import FULL_SIZE_LINK_TEXT, render_for_devto


def png(width: int, height: int = 10) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def test_png_size_reads_the_header():
    assert png_size(png(3280, 974)) == (3280, 974)
    assert png_size(b"not a png") is None


def test_budget_math():
    # 12px labels must stay >= 11px in an 800px column -> at most ~872px drawn width.
    assert max_drawn_width(800, 11.0) == 872


def test_wide_diagram_is_flagged_with_actionable_feedback():
    finding = column_width_finding(png(3280), column_px=800, min_text_px=11.0)  # drawn at 2x -> 1640px
    assert finding is not None and finding.check == "column_width"
    assert "1640px wide" in finding.message and "5.9px" in finding.message and "TB" in finding.message


def test_diagram_within_budget_passes():
    assert column_width_finding(png(1600), 800, 11.0) is None   # 800px drawn: labels at full 12px
    assert column_width_finding(png(1740), 800, 11.0) is None   # 870px drawn: labels ~11.03px
    assert column_width_finding(None, 800, 11.0) is None


async def test_render_flags_wide_drawio_render_as_lint(monkeypatch):
    from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec
    from src.modules.diagrams.usecases import generate_diagram_usecase as mod

    class Renderer:
        async def render_drawio(self, xml, embed_diagram=True):
            return SimpleNamespace(svg="<svg/>", png_bytes=png(3000), sha256="x")

    spec = DiagramSpec.model_validate({
        "title": "Pipeline", "type": "flowchart", "direction": "LR",
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
    })
    usecase = mod.GenerateDiagramUsecase(models=None, renderer=Renderer(), repository=None,
                                         settings=SimpleNamespace(diagram_column_width_px=800, diagram_min_text_px=11.0))
    candidate = await usecase._render(spec, "drawio")
    assert any(f.check == "column_width" for f in candidate.lint)
    assert candidate.major >= 1
    assert "800px column" in mod.review_feedback(candidate)


class Uploader:
    async def upload_asset(self, src, alt="", title=""):
        return "key", "https://bucket.s3.amazonaws.com/diagrams/abc.png"


async def test_devto_render_links_full_size_diagram_only_for_assets():
    revision = SimpleNamespace(
        markdown='# T\n\nIntro.\n\n![Arch](asset://123 "Arch")\n\n![Shot](/img/shot.png "Shot")\n',
        slug="t", tags=[], metadata={}, title="T", description="d",
    )
    result = await render_for_devto(revision=revision, canonical_url="https://site/posts/t", uploader=Uploader())
    link = FULL_SIZE_LINK_TEXT.format(url="https://bucket.s3.amazonaws.com/diagrams/abc.png")
    assert result.body_markdown.count(link) == 1
    assert f'"Arch")\n\n{link}' in result.body_markdown
