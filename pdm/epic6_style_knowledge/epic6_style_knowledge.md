# Epic 6 — Personal Style & Knowledge Base

| | |
|---|---|
| **Milestone** | M2 |
| **Depends on** | Epic 3 (drafting); works best after Epic 5 (published posts exist) |
| **Status** | Draft for review |

## Goal

Make drafts sound like the owner by learning from the owner's own articles:

- import existing posts and approved samples
- derive an editable **style profile**
- retrieve only the relevant past examples (and the owner's notes) while outlining and drafting
- never copy large passages verbatim

## Context
- Existing corpus:
  - Sanity `post` documents, where `content` is Markdown
  - `blogs/**/*.md` (today, the `fine_tuning` series)
- The static style guide from Epic 3 (E3-S2) stays as the fallback and the seed.
- pgvector is introduced **only now**, using the Postgres image from Epic 1.

## In scope
- Sample import from Sanity and the local folder.
- Chunking and embeddings in pgvector.
- Style profile generation and editing.
- Retrieval in the outline and draft nodes.
- A copy-detection check.
- An internal-link suggestion feature.
- Owner notes.

## Out of scope
- Fine-tuning a model on the owner's style.
- Long-term conversational memory.

---

## Stories

### E6-S1 — Enable pgvector & embeddings configuration
**As** a developer, **I want** vector storage and a configurable embedding model, **so that** semantic retrieval works locally.

**Acceptance criteria**
- [ ] An Alembic migration runs `CREATE EXTENSION IF NOT EXISTS vector`. The `sample_chunks` table has `embedding vector(<dim>)` and an HNSW index (cosine).
- [ ] The embedding model is configured as `EMBEDDING_MODEL` (`provider:model`) through LangChain `init_embeddings`. The dimension is read from config and validated at startup.
- [ ] Output port `IVectorStore` (`upsert_chunks`, `similarity_search(query, k, filters)`). The adapter uses SQLModel with the `pgvector` SQLAlchemy type, or `langchain-postgres` `PGVector`. Pick one and document why.

**Size:** 3

---

### E6-S2 — Import existing posts as writing samples
**As** the owner, **I want** my existing articles imported with one action, **so that** the agent learns from real examples.

**Acceptance criteria**
- [ ] `POST /samples/import` takes `{sources: ["sanity","local"]}`.
  - **Sanity:** a GROQ query for all `post` documents fetching `_id, title, description, tags, publishedAt, content`.
  - **Local:** all `blogs/**/*.md` files, with the title taken from the first H1.
  - Items are de-duplicated by `.publish-meta.json` mapping, then by content hash.
- [ ] Each sample (`writing_samples`) stores `origin`, `remote_id`/path, title, tags, `published_at`, `approved_as_style_example` (default true), and the full Markdown.
- [ ] Chunking is by H2/H3 section, with heading path kept as metadata (`"2. LoRA > 2.1 Rank"`). Code blocks stay inside their section. Chunks are embedded and upserted.
- [ ] Re-import is idempotent: changed content is re-embedded and unchanged content is skipped.
- [ ] A Style page in the UI lists the samples. Each one has a toggle for "use as style example" and a "re-import" button.

**Size:** 3

---

### E6-S3 — Generate & edit a style profile
**As** the owner, **I want** an explicit, editable description of my style, **so that** I can correct what the AI thinks my style is.

**Acceptance criteria**
- [ ] `POST /style-profile/generate` analyses approved samples, sampled per section type. It returns a structured `StyleProfile`:
  - `tone`
  - `voice`
  - `structure_patterns` (by format)
  - `heading_conventions`
  - `intro_pattern`
  - `explanation_devices` (analogies, "In simple terms", tables)
  - `code_example_style`
  - `diagram_usage`
  - `typical_length` (by format)
  - `do[]` and `dont[]`
  - `signature_phrases[]` (short only)
- [ ] Profiles are versioned (`style_profiles`) and exactly one is `active`. The owner can edit the profile in a form (RHF + Zod) or as Markdown, and the edit creates a new version.
- [ ] The drafting prompts use the **active profile**, and the Epic 3 static style guide when no profile exists. The profile version is recorded in revision metadata and in LangSmith metadata.

**Size:** 3

---

### E6-S4 — Retrieve relevant examples during outline & drafting
**As** the owner, **I want** the agent to look at my most similar past sections while writing, **so that** structure and tone match without generic AI prose.

**Acceptance criteria**
- [ ] `create_outline` retrieves the top-k (default 3) sample **outlines** (heading trees) of the same `format`.
- [ ] `draft_article` retrieves the top-k (default 2) sample **sections** for each section, using the section goal as the query.
- [ ] Retrieved examples are budgeted by tokens (e.g. at most 1.5k tokens per section prompt) and labelled "style reference — do not copy".
- [ ] Retrieval can be turned off per task (`use_style_examples`). The ids of the retrieved chunks are stored in revision metadata for traceability.
- [ ] A/B check (manual, documented): the same topic drafted with retrieval on and off, compared by the judge's `style_adherence` score (Epic 9 automates this).

**Size:** 3

---

### E6-S5 — Copy-detection validator
**As** the owner, **I want** drafts checked for verbatim reuse of my old posts or of sources, **so that** new articles are original.

**Acceptance criteria**
- [ ] A deterministic validator computes word 8-gram overlap between the draft and (a) the retrieved samples and (b) the extracted source texts. Code blocks and quoted citations are excluded.
- [ ] A section with more than 15% overlap, or any run of more than 40 identical words, is flagged as a `warning`. More than 30% is flagged as a `blocker`, which triggers self-revision.
- [ ] Thresholds are configurable and the results appear in the Issues panel.

**Size:** 2

---

### E6-S6 — Internal link & series suggestions
**As** the owner, **I want** the agent to link to my related posts correctly, **so that** series and cross-references work on the site (unlike relative `.md` links today).

**Acceptance criteria**
- [ ] While drafting, the agent retrieves up to 3 related published posts by embedding similarity. It may only link to them with absolute URLs: `https://leon-pham.vercel.app/posts/<_id>`.
- [ ] For `format=series_part`, it adds "previous part" / "next part" links using `series.previous_post_id`.
- [ ] The validator checks that every internal link points to an existing post id. The post list is cached from Sanity.

**Size:** 2

---

### E6-S7 — Owner notes knowledge base
**As** the owner, **I want** to add my own notes (Markdown or text) to the knowledge base, **so that** the agent can use my experience as a source alongside the web.

**Acceptance criteria**
- [ ] `POST /notes` (paste or upload `.md`/`.txt`, maximum 1 MB) is chunked and embedded with `origin=owner_note`.
- [ ] During research (Epic 2), notes relevant to the plan questions are retrieved as sources of type `owner_note`, with quality fixed by the owner. They can support claims, and they appear in the Sources panel. They are **never** cited as public references unless the owner marks them as citable with a URL.
- [ ] Notes can be listed, edited and deleted from the Style page.

**Size:** 3

---

## Definition of done (epic)
- Existing posts are imported, and a style profile has been generated and edited by the owner.
- A new draft with retrieval on scores higher on `style_adherence` than one with retrieval off (judged on at least 3 topics).
- The copy-detection check catches a planted copied paragraph.
- Internal links resolve on the live site.

## Learning map
| Tool | Concepts |
|---|---|
| LangChain | Embeddings (`init_embeddings`), document loaders, text splitters by Markdown headers, vector store retrievers, metadata filters |
| LangGraph | Injecting retrieval results into node context, per-task feature flags in state |
| LangSmith | Comparing retrieval on/off runs, inspecting retrieved docs in traces |
