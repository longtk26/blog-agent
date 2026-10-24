# Epic 8 — DEV Community Publishing

| | |
|---|---|
| **Milestone** | M4 |
| **Depends on** | Epic 5 (gate, publication records, render transform); Epic 7 for Mermaid SVG fallback |
| **Status** | Complete |

## Goal

Publish approved revisions to DEV Community (dev.to) as a draft or live, in the mode that was explicitly approved. Publishing:

- uses the same approval gate and idempotency guarantees as Sanity
- transforms the Markdown so it renders correctly on Dev.to
- sets `canonical_url` to the owner's site

## Context (confirmed from profile-ui `/api/publish`)
- The existing flow:
  - calls `POST/PUT https://dev.to/api/articles` with an `api-key` header and `published: false`
  - sends `tags.slice(0,4)`
  - sends `main_image` only for raster images
  - strips the H1
  - converts LaTeX to code with `formatMathForDevTo`
- Dev.to (Forem) does **not** render Mermaid or KaTeX `$…$`. It also needs public image URLs, and the Sanity CDN URLs from Epic 5 work for this.
- API behaviour must be **re-verified against current Forem docs** before implementation (brief §6 M4).

## In scope
- API verification spike.
- Dev.to render transform.
- Dev.to adapter with idempotency.
- Draft/live modes bound to approval.
- Rate limiting.
- UI status.

## Out of scope
- Cross-posting to other platforms (Medium, Hashnode).
- Comments or analytics sync.

---

## Stories

### E8-S1 — Spike: verify current DEV/Forem API
**As** a developer, **I want** the current Dev.to API capabilities confirmed, **so that** the adapter is built on facts, not assumptions.

**Acceptance criteria**
- [x] A short doc (`pdm/epic8_devto_publishing/devto_api_notes.md`) records:
  - base URL and API version header (`accept: application/vnd.forem.api-v1+json`)
  - auth (`api-key`)
  - create and update endpoints
  - listing own articles (including unpublished)
  - fields: `title`, `body_markdown`, `published`, `tags` (maximum 4, and their rules), `canonical_url`, `main_image`, `series`, `description`, `organization_id`
  - rate limits and error formats
  - whether unpublishing is possible through the API
- [x] Verified with a throwaway draft article on the owner's account. This requires owner consent at execution time, and the article is deleted or unpublished afterwards.

**Size:** 2

---

### E8-S2 — Dev.to render transform
**As** the owner, **I want** my article converted to Dev.to-compatible Markdown automatically, **so that** it looks right there without manual edits.

**Acceptance criteria**
- [x] `render_for_devto(revision, sanity_render?)` is deterministic and makes these changes:
  - removes the leading H1, because the title is a separate field
  - converts KaTeX: inline `$x$` → `` `x` ``; block `$$…$$` → a fenced `text` block, or Dev.to's `{% katex %}` liquid tag if the spike confirms it is supported
  - replaces each Mermaid fence with its rendered SVG/PNG image (from Epic 7, uploaded to the Sanity CDN), with a caption
  - makes TOC anchors match Dev.to's heading id scheme, or drops the TOC if they can't
  - rewrites internal `/posts/<id>` links to absolute site URLs
  - adds an optional footer: "Originally published at <canonical_url>"
- [x] `main_image` is the cover image only if it is raster (PNG/JPG), as today. SVG covers are converted to PNG by the renderer.
- [x] `canonical_url` is the Sanity site URL when Sanity is also a destination of the same approval, or when the post was already published there.
- [x] Golden-file tests run on the two existing fine-tuning posts. The rendered output is kept as `rendered_content_hash` and stored for audit.

**Size:** 3

---

### E8-S3 — Dev.to adapter with idempotency
**As** the owner, **I want** retries and republishing to update the same Dev.to article, **so that** I never get duplicate posts.

**Acceptance criteria**
- [x] `DevtoPublisher` implements `IPublisher` using `httpx`. The API key (`DEV_TO_API_KEY` in `blog-agent/.env`) is sent only as a header and never logged or traced.
- [x] First publish:
  1. Before creating, list the owner's articles (`/api/articles/me/all`, paginated) and match on `canonical_url` or exact title. This catches the case where an earlier attempt timed out but actually succeeded.
  2. If there is a match, adopt that id and `PUT`. Otherwise `POST`.
- [x] Later publishes `PUT` to the stored `remote_document_id`.
- [x] Status `429` is retried with the `Retry-After` delay up to 3 times. 4xx validation errors (e.g. bad tags) fail immediately, and the server message is shown.
- [x] The adapter records the remote id, `url`, `published` state and `published_at`.

**Size:** 3

---

### E8-S4 — Draft vs live mode bound to approval
**As** the owner, **I want** to choose explicitly whether Dev.to gets a draft or a live post, **so that** going public is always a deliberate decision.

**Acceptance criteria**
- [x] The approval for `destination=devto` carries `options.mode`: `draft` (default, `published:false`) or `published`.
- [x] The gate checks that the mode being published equals the approved mode.
- [x] Switching an existing Dev.to draft to live requires a new approval with `mode=published` on the current revision.
- [x] The approval dialog (E4-S6) shows a clear warning for `published`.

**Open decision:** D8.

**Size:** 2

---

### E8-S5 — UI: Dev.to status & actions
**As** the owner, **I want** to see the Dev.to article's state and jump to it, **so that** I can finish it on Dev.to if needed.

**Acceptance criteria**
- [x] The publication panel shows a Dev.to row with mode (draft/live), remote link (the Dev.to edit URL for drafts), last sync, attempts and errors.
- [x] "Retry" retries only the failed destination. A successful Sanity publication is never re-run.
- [x] A rendered Dev.to preview tab shows the transformed Markdown in a basic renderer and notes that Dev.to styling differs.

**Size:** 2

---

## Definition of done (epic)
- An article approved for `sanity + devto(draft)` publishes to both. The Dev.to draft:
  - has the canonical URL pointing at leon-pham.vercel.app
  - shows Mermaid as images
  - shows math as code/katex
  - has at most 4 valid tags
- A simulated timeout followed by a retry produces no duplicate. Re-approval and republish update the same Dev.to article.

## Learning map
| Tool | Concepts |
|---|---|
| (Mostly integration work) | Adapter pattern behind ports, idempotent external writes, golden-file testing of deterministic transforms |
| LangSmith | Correlating publish outcomes with the generating run for later evaluation |
