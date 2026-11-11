# Epic 14 — Diagram Readability on DEV

| | |
|---|---|
| **Milestone** | M3.2 |
| **Depends on** | Epic 10 (review/regeneration loop, layout lint), Epic 12 (S3 originals) |
| **Status** | Implemented 2026-11-11: awaiting owner review (draft on DEV to inspect) |

## Problem (owner report: "images on dev.to are blurry")
DEV serves every body image through `media2.dev.to/dynamic/image/width=800,fit=scale-down,format=auto/<url>`: it
**always scales images down to 800px wide and re-encodes them as lossy WebP**. The click-through link is that same copy.
This can't be configured. Our diagrams were far too wide for it:

| Diagram (PNG at 2x) | Drawn width | Shown on DEV | 12px labels shown at |
|---|---|---|---|
| 2984×764 (Sanity-era) | 1492px | 800×205 | 6.4px |
| 3280×974 / 3848×636 (recent agent output) | 1640 / 1924px | 800×238 / 800×132 | 5.9 / 5.0px |
| **964×1639 (this epic, first live run)** | **482px** | **800×1360** | **≥12px** |

Raising the font size doesn't help: `geometry.py` sizes every box from the text, so bigger text makes a proportionally
wider diagram, which DEV shrinks by the same factor. The lever is the drawn width.

## Stories
| # | Story | Pts |
|---|---|---|
| S1 | `diagrams/domain/readability.py`: read the PNG width from its header; if 12px labels would fall below `DIAGRAM_MIN_TEXT_PX` (11) in a `DIAGRAM_COLUMN_WIDTH_PX` (800) column (i.e. drawn width > ~872px), add a `column_width` **layout-lint finding**. Lint counts as a major issue, so the existing loop regenerates the spec with actionable feedback (TB, ≤3-4 nodes side by side, split) and keeps the best round | 3 |
| S2 | Diagram prompt `diagram-v3`: TB first; LR only for short chains of ≤4; ≤3-4 nodes side by side | 1 |
| S3 | Dev.to render: `*[Open the full-size diagram](<original>)*` under every `asset://` diagram (the original on S3 is full resolution) | 1 |
| S4 | profile-ui: strip that line (the site already shows originals) | 1 |
| S5 | Log which checks failed in each regeneration round | 0.5 |

Replaced from the proposal: an "is it readable at 800px?" item for the vision checklist. A deterministic width check
is exact and cheaper than asking a model to judge legibility.

## Verified
- Unit 439 passed (6 new in `tests/unit/diagrams/test_readability.py`); `make test-integration` 475 passed; Dev.to golden unchanged; profile-ui `tsc` clean.
- **Live**, on `agy:gemini-3.8-flash-medium`: a new article task ("How a request travels through Kubernetes: Ingress, Service
  and Pods", draw.io diagram forced, DEV only) → round 0 had 1 major issue (which kind wasn't logged then, so S5 was added),
  round 1 passed → TB diagram 964×1639 (482px drawn), real GCP/K8s stencils, readable labels.
- Approved for DEV in **draft** mode and published: DEV article 5017893, `published: false`. The body uses the S3 PNG plus the
  full-size link; `media2.dev.to` serves it at 800×1360.

## Not verified / notes
- Already-published DEV posts keep their old wide diagrams until they are regenerated and republished.
- Mermaid diagrams are unaffected (DEV renders them natively as vector).
