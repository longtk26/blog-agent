# Epic 5 — Sanity Publishing

| | |
|---|---|
| **Milestone** | MVP |
| **Depends on** | Epic 4 |
| **Status** | Draft for review |

## Goal

Publish an approved revision to the owner's Sanity dataset so that it appears on leon-pham.vercel.app. Publishing:

- happens only after the approval gate passes
- is idempotent, so retries never create duplicates
- uploads assets
- preserves `publishedAt` on updates
- records every outcome

Optionally, it also keeps the local `blogs/` folder and `.publish-meta.json` in sync with the existing blog-manager.

## Context (confirmed)
- Sanity project `demmqb6o`, dataset `blogs`. The site client uses `apiVersion: "2025-01-20"`.
- `post` fields that must be written:
  - `title`, `description`
  - `image`: cover, an asset reference
  - `images[]`: `{_key, _type:'image', asset, alt, caption}`
  - `tags[]`: `{_key, _type:'tag', value}`
  - `publishedAt`, `updatedAt`
  - `content`: Markdown string
- There are no other fields. Writing unknown fields would show warnings in Studio, so the agent must not add any.
- The site routes by `_id`. With a deterministic, slug-like `_id` (decision D5), URLs become `https://leon-pham.vercel.app/posts/<slug>`.
- The current profile-ui publish route resets `publishedAt` on every publish and overwrites local Markdown with CDN URLs. This epic avoids both problems.
- The write token (`SANITY_API_WRITE_TOKEN`, Editor role) exists today in profile-ui's env. The agent gets **its own** token in `blog-agent/.env`.

## In scope
- Publish gate use case.
- Publication records.
- Sanity HTTP adapter.
- Asset upload and the render transform.
- Publish/retry API and UI.
- Optional export to `blogs/`.
- Updating an already-published article.

## Out of scope
- Dev.to (Epic 8).
- Changes to the profile-cms schema (none are required; see the optional story).

---

## Stories

### E5-S1 — Publish use case enforcing the approval gate
**As** the owner, **I want** publishing to be impossible without a valid approval, **so that** a bug, a model output or a stray request can never publish unapproved content.

**Acceptance criteria**
- [ ] `PublishRevisionUsecase.execute(revision_id, destinations)` runs these steps:
  1. Load the revision.
  2. For **each** destination, call `ApprovalGate.check` (Epic 4). If it fails, raise `ForbiddenException(code=APPROVAL_REQUIRED|APPROVAL_STALE|HASH_MISMATCH)`.
  3. Move the task to `publishing`.
  4. Call the destination adapter.
  5. Record the outcome.
  6. Move the task to `published`, `partially_published` or `failed`.
- [ ] The publishing adapters can only be reached through this use case. The LangGraph graph **has no publishing tool**: publishing is triggered by an owner API call, not by the model.
- [ ] A per-task lock (Postgres advisory lock) prevents two concurrent publishes of the same task.
- [ ] Tests:
  - every gate failure path returns 403 and makes no adapter call (mock asserts zero calls)
  - concurrent publish requests → only one runs

**Size:** 3

---

### E5-S2 — Publication records & idempotency
**As** the owner, **I want** each publish attempt recorded and safely retryable, **so that** I can see what happened and retry without duplicates.

**Acceptance criteria**
- [ ] `publications` table:
  - `id`, `task_id`, `article_revision_id`, `destination`
  - `remote_document_id`, `remote_url`
  - `status` (`pending`, `succeeded`, `failed`)
  - `attempt_count`
  - `rendered_content_hash`
  - `last_error` (sanitised)
  - `published_at`, `updated_at`
  - Unique constraint on `(task_id, destination)`. A task maps to one remote document per destination, and later revisions update it.
- [ ] The Sanity `_id` is deterministic: `slug`, validated `^[a-z0-9][a-z0-9-]{2,79}$` with no dots. It is stored on the first successful publish and never changes after that, even if the slug metadata changes later.
- [ ] Retrying a destination that already succeeded for the same revision is a no-op that returns the existing result.
- [ ] Retries are bounded: 3 attempts with exponential backoff for 5xx/timeouts. Errors that are not retryable (4xx) fail immediately with a clear message.

**Size:** 3

---

### E5-S3 — Sanity adapter (HTTP API)
**As** a developer, **I want** a typed Sanity adapter that writes posts matching the existing schema, **so that** agent posts look identical to hand-published ones on the site.

**Acceptance criteria**
- [ ] `SanityPublisher` implements the `IPublisher` port using `httpx`. Endpoints:
  - Mutations: `POST https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync`
  - Documents: `GET .../data/doc/blogs/{id}`
  - Assets: `POST .../assets/images/blogs`
  - Project id, dataset and API version all come from config.
- [ ] Before the first publish, a **collision check** runs. If a document with that `_id` exists and is not in our `publications` table, publishing fails with `SLUG_TAKEN`, and the UI asks for a new slug, which means a new revision and a new approval.
- [ ] Each publish is one atomic transaction of mutations:
  1. `createIfNotExists {_id, _type:"post"}`
  2. `patch {set: {title, description, image, images, tags, content, updatedAt}, setIfMissing: {publishedAt: now}}`

  This **preserves `publishedAt` on updates**, which fixes the reset bug in today's flow.
- [ ] `tags` and `images` items get stable `_key`s, derived from a hash of the value or asset, so updates don't churn keys.
- [ ] After publishing, the document is read back to confirm that `content` equals the rendered Markdown (by hash). The remote URL is `https://leon-pham.vercel.app/posts/{_id}` and the Studio URL is recorded too.
- [ ] The token is sent only in the `Authorization` header. It is never logged or traced: the adapter runs outside LangChain callbacks, and the log redaction filter is active.
- [ ] Contract tests use recorded responses (`respx`). One opt-in live test writes to a **separate test dataset** (e.g. `blogs-test`) and runs only if `SANITY_TEST_DATASET` is set.

**Open decision:** D4. If a "Sanity draft" destination is wanted, the same adapter writes `_id = drafts.<slug>` and the owner publishes from Studio.

**Size:** 5

---

### E5-S4 — Asset upload & publish-time render transform
**As** the owner, **I want** local images and diagrams uploaded and linked automatically, **so that** I never hand-edit CDN URLs and the approved revision itself stays untouched.

**Acceptance criteria**
- [ ] A deterministic `render_for_sanity(revision)` function:
  1. Finds local asset references in the Markdown: `![alt](asset://<id>)` or relative asset paths.
  2. Uploads each asset to Sanity (`assets/images`). Sanity de-duplicates by content hash, so re-uploads return the same asset id.
  3. Rewrites the references to CDN URLs.
  4. Builds `images[]` with `alt` and `caption` (caption from the image title when present).
  5. Chooses the cover: the first raster or SVG image, or the cover chosen in metadata.
- [ ] The **stored, approved revision is never modified**. The rendered Markdown is a derived artefact: its hash is stored as `rendered_content_hash` and its content is kept for audit.
- [ ] The transform is pure and deterministic given the same asset uploads. Unit tests use fixtures that include the existing posts' image syntax (`![alt](src "title")`).
- [ ] SVG uploads are sanitised first: scripts, event handlers and external references are stripped.

**Size:** 3

---

### E5-S5 — Publish & retry API + UI
**As** the owner, **I want** to click "Publish" after approving and see the result with a link, **so that** I know the post is live.

**Acceptance criteria**
- [ ] `POST /revisions/{id}/publish` takes `{destinations: ["sanity"]}` and returns per-destination results: `{destination, status, remote_url, error?}`.
- [ ] `GET /tasks/{id}/publications` lists all records.
- [ ] UI:
  - After approval, a **Publish** button appears. It is disabled unless a valid approval exists, and the server enforces this anyway.
  - The publication panel shows each destination's status, the remote link, a Studio link, the attempt count and the last error.
  - Failed destinations get a "Retry" button.
- [ ] Progress events (`publishing_started`, `asset_uploaded`, `publish_succeeded/failed`) stream over the existing SSE channel.
- [ ] **Spike:** check whether profile-ui caches `/blogs` and `/posts/[id]` (Next.js data cache / ISR). If it does, document how to make a new post appear, e.g. a revalidation webhook or a `revalidate` export. If a code change in profile-ui is needed, raise a separate story.

**Size:** 3

---

### E5-S6 — Update an already-published article
**As** the owner, **I want** to revise a published post and republish it, **so that** I can fix or extend articles later.

**Acceptance criteria**
- [ ] On a `published` task, the owner can edit or request a revision. That produces a new revision, moves the task to `awaiting_review`, and requires a new approval (Epic 4 rules).
- [ ] Republishing updates the same `_id`. `publishedAt` is preserved, `updatedAt` is set, and `publications.article_revision_id` moves to the new revision. The history of what was published and when is kept in `task_events`.
- [ ] **Unpublish** (delete from Sanity) is a separate destructive action. It uses its own confirmation dialog (type the slug), records an event, and is not reachable from the graph.

**Size:** 3

---

### E5-S7 — Optional export to local `blogs/` folder
**As** the owner, **I want** published agent posts saved into my `blogs/` folder, **so that** my content stays versioned in git and visible in the existing blog-manager.

**Acceptance criteria**
- [ ] `BLOGS_EXPORT_ENABLED=true` takes effect only when `../blogs` is mounted (Epic 1). After a successful Sanity publish, the exporter writes:
  - `blogs/<folder>/<slug>.md` containing the **rendered** Markdown (CDN URLs). `folder` comes from the series name or a task field, defaulting to the slug.
  - `blogs/<folder>/diagrams/*.drawio|svg`, once Epic 7 exists.
  - The `.publish-meta.json` entry `"<folder>/<slug>": {"sanity": "<_id>", "devto": "<id?>"}`. This is a merge-write. Other keys are left untouched, and the write is atomic (temp file + rename).
- [ ] The exporter never overwrites a file it didn't create. It tracks the files it owns; on a conflict it writes `<slug>.agent.md` and warns.
- [ ] The README notes that republishing an agent post from profile-ui's blog-manager will reset `publishedAt` and replace tags (current behaviour). It recommends publishing agent posts from the agent.

**Open decision:** D6.

**Size:** 2

---

### E5-S8 — *(Optional, outside blog-agent)* profile-ui / profile-cms hardening
**As** the owner, **I want** small fixes in my site repos that the analysis surfaced, **so that** agent-published posts behave well everywhere.

These items are listed for the owner's review. Each would become a story in the respective repo if accepted.
- [ ] profile-ui `/api/publish`: preserve `publishedAt` on update (`setIfMissing`).
- [ ] profile-ui `getPostDetails`: also fetch `description` for `<meta>` / SEO.
- [ ] profile-ui `MarkdownComp`: add `rehype-sanitize` with an allowlist.
- [ ] profile-ui: protect `/blog-manager` and `/api/publish|local-blogs` (for example, disable them when `NODE_ENV=production`).
- [ ] profile-cms: add basic `validation` (required title/content, description ≤ 160).

**Size:** n/a (separate repos)

---

## Definition of done (epic)
- An approved article from Epic 4 is published to Sanity with one click and appears at `https://leon-pham.vercel.app/posts/<slug>` with its cover, tags and description.
- Retrying creates no duplicate.
- Editing and republishing keeps `publishedAt`.
- Every gate-failure test passes with zero adapter calls.
- With export enabled, `blogs/` and `.publish-meta.json` are updated correctly.

## Learning map
| Tool | Concepts |
|---|---|
| LangGraph | Keeping side-effecting operations **outside** the graph, or behind an explicit human-triggered resume. Why publishing is not a model tool |
| LangSmith | Linking the publish event to the originating trace via `task_id` metadata |
