"""Will a rendered diagram still be readable in an article column? (Epic 14)

DEV (dev.to) serves every body image through its resizer at a fixed 800 px width (`media2.dev.to/dynamic/image/
width=800,fit=scale-down,format=auto/...`, verified 2026-11-11), re-encoded as lossy WebP. A wide diagram is
shrunk to fit, and its labels with it: a 3280 px PNG (1640 px drawn at 2x) shows 12 px labels at ~5.9 px.

Raising the font size does not help, because the geometry sizes every box from the text, so a diagram with bigger
text is proportionally wider and is shrunk by the same factor. The lever is the diagram's drawn width.
"""

import struct

from src.modules.diagrams.domain.geometry import NODE_FONT
from src.modules.diagrams.domain.layout_lint import LintFinding

# renderer/server.js exports draw.io PNGs with `-s 2`.
DRAWIO_PNG_SCALE = 2
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(png: bytes) -> tuple[int, int] | None:
    """(width, height) from the IHDR chunk, without decoding the image."""
    if len(png) < 24 or not png.startswith(PNG_SIGNATURE) or png[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", png[16:24])


def max_drawn_width(column_px: int, min_text_px: float, font_px: float = NODE_FONT) -> int:
    """Widest drawn diagram whose labels stay at least `min_text_px` tall when fitted into `column_px`."""
    return int(column_px * font_px / min_text_px)


def column_width_finding(
    png: bytes | None,
    column_px: int,
    min_text_px: float,
    scale: int = DRAWIO_PNG_SCALE,
    font_px: float = NODE_FONT,
) -> LintFinding | None:
    """A layout finding when the diagram is too wide for its labels to stay readable; None when it fits."""
    size = png_size(png) if png else None
    if size is None:
        return None
    drawn_width = size[0] / scale
    shown_text = font_px * min(1.0, column_px / drawn_width)
    if shown_text >= min_text_px:
        return None
    limit = max_drawn_width(column_px, min_text_px, font_px)
    return LintFinding(
        check="column_width",
        message=(
            f"The diagram is {drawn_width:.0f}px wide. Articles show it in a {column_px}px column, so its "
            f"{font_px:g}px labels shrink to {shown_text:.1f}px and can't be read. Make it at most ~{limit}px wide: "
            "use direction TB, keep at most 3-4 nodes side by side, shorten labels, or drop nodes the text already "
            "explains (split a big system into two diagrams if needed)."
        ),
    )
