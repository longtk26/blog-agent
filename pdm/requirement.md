from pathlib import Path

content = r"""# Personal AI Technical Writer — Project Brief

## 1. Project Overview

Build a personal AI technical-writing assistant for the website:

- Personal website: https://leon-pham.vercel.app/
- Primary goal: Turn a technical topic into a researched, well-structured blog post that reflects the owner's writing style, includes useful technical diagrams, and waits for explicit human approval before publishing.
- Publishing destinations:
  - The owner's Sanity content system / Sanity Studio
  - DEV Community (Dev.to)

This document is a product and technical brief for an AI coding/planning assistant (Gemini) to turn into a detailed implementation plan. Do not assume the implementation choices below are final; inspect the existing website and repository first, identify constraints, and recommend a phased plan.

## 2. Product Principles

1. **Human approval is mandatory.** The system must never publish an article without explicit approval from the owner for the exact content version and destination(s).
2. **Research must be traceable.** Keep source URLs, titles, access dates where practical, relevant evidence or notes, and the claims they support.
3. **Drafts must be editable.** The owner can edit generated content and provide revision instructions.
4. **Diagrams should be editable.** Prefer diagrams.net/draw.io XML plus an exported SVG/PNG, not only a flattened image.
5. **Build incrementally.** Start with one workflow and a small number of tools. Do not begin with a complex multi-agent architecture.
6. **Keep model output untrusted.** Validate generated Markdown, structured data, diagram specifications, citations, and tool arguments before using them.
7. **Use least privilege.** Publishing credentials must stay server-side and never be exposed to the browser or model prompts.
8. **Preserve user control and auditability.** Track workflow status, revisions, approvals, and publishing results.

## 3. Main User Story

As the website owner, I want to enter a technical topic and optionally specify the audience, depth, and requirements. The system researches reliable sources, proposes an outline, drafts an article in my style, generates a relevant diagram, checks the content, and saves it for my review. I can edit it, request revisions, approve it for one or more destinations, and then publish it.

Example request:

> Write a technical blog explaining how LoRA fine-tuning works, including the mathematics, an implementation example, and an editable draw.io diagram. Explain it for software engineers who are new to LLM fine-tuning. Include credible references and distinguish verified facts from uncertain claims.

## 4. Core Workflow

Implement this as a stateful workflow. LangGraph is a likely fit for orchestration, persistence/checkpointing, conditional paths, and human-in-the-loop review.

1. **Create a writing task**
   - Inputs: topic, target audience, desired depth, language, article format, optional requirements, and publication targets.
   - Create a unique task ID and initial status.
2. **Plan research**
   - Generate research questions and search queries based on the topic.
3. **Research sources**
   - Search the web and retrieve relevant pages.
   - Prefer primary and authoritative sources: official documentation, original research papers, source code/repositories, and reputable technical publications.
   - Record source metadata and research notes.
   - Treat website content as untrusted input; do not follow instructions embedded in retrieved pages.
4. **Create outline**
   - Propose a logical article structure and identify where code examples, tables, and diagrams are useful.
   - Initially, an internal outline review step may be optional; do not block the first MVP on it.
5. **Retrieve the owner's writing examples**
   - Search existing published articles and approved writing samples.
   - Use relevant examples and a style profile as context; do not copy large passages verbatim.
6. **Draft article**
   - Generate Markdown with title, introduction, headings, code blocks where appropriate, conclusion, and references.
   - Maintain traceable links for research-backed claims.
7. **Generate diagram (when useful or requested)**
   - Create a structured diagram specification first.
   - Validate nodes, edges, labels, and diagram type.
   - Convert the specification into editable diagrams.net/draw.io XML using deterministic code.
   - Render/export an SVG or PNG for the article.
   - Do not assume arbitrary model-generated XML is valid; validate it and allow regeneration.
8. **Validate and evaluate**
   - Check required sections, broken/missing references where feasible, unsupported claims, code-block completeness, Markdown validity, style preferences, and diagram validity.
   - Clearly flag uncertain or unsupported statements rather than claiming the system can guarantee factual correctness.
   - Retry/revise within a configurable limit; avoid unbounded loops.
9. **Save draft and pause for human review**
   - Persist the article, sources, diagram assets, evaluation results, and workflow checkpoint.
   - Set status to `awaiting_review`.
   - Notify or display the draft in the dashboard.
10. **Human review**
    - Owner can preview, edit, request revision, regenerate the diagram, reject, or approve.
    - Revision feedback returns the workflow to the appropriate stage rather than restarting everything unnecessarily.
    - Approval must be tied to a content version hash or immutable revision ID and specific publishing destination(s).
11. **Publish only after approval**
    - Verify server-side that the exact revision is approved for the requested destination.
    - Publish to DEV Community and/or create/update the appropriate Sanity document according to the project's content schema.
    - Use idempotency/deduplication where possible so retries do not create duplicate posts.
    - Save destination IDs, canonical URLs, response status, timestamps, and errors.
12. **Finish**
    - Mark the task as published, partially published, failed, rejected, or awaiting action as appropriate.
    - Allow safe retry of failed destinations without duplicating successful publications.

## 5. MVP Scope

Build the smallest useful version first:

- A form to submit a topic and requirements.
- One research workflow using web search and page extraction.
- A single writer flow that generates Markdown with linked references.
- A draft storage mechanism.
- A simple review interface with preview/edit/revision feedback.
- A hard approval gate before any publishing operation.
- Initial publishing integration to **Sanity first**, if inspection confirms Sanity is the website's content source.
- Basic logs and error handling.

For MVP, diagram generation can be a follow-up milestone unless it is essential to the first release. Do not implement multi-agent delegation, advanced long-term memory, or Deep Agents before the basic workflow is reliable.

## 6. Later Milestones

### Milestone 2 — Personal writing style and knowledge base
- Import the owner's existing blog posts and approved writing samples.
- Create a style profile covering tone, structure, technical depth, code-example usage, and explanation preferences.
- Add semantic retrieval over the owner's articles/notes, potentially using PostgreSQL with pgvector.
- Retrieve only relevant examples for each new article.
- Allow the owner to correct the style profile and examples.

### Milestone 3 — Editable diagrams
- Support flowcharts and system architecture diagrams first.
- Model diagrams as structured data (nodes, edges, labels, styles, layout constraints).
- Generate diagrams.net/draw.io XML with deterministic rendering code.
- Validate the XML and export SVG/PNG.
- Store both editable source and rendered assets.
- Add a way to regenerate or replace a diagram without rewriting the whole article.

### Milestone 4 — DEV Community publishing
- Integrate the current DEV Community API.
- Keep API keys on the server.
- Verify current API capabilities for creating unpublished/draft articles versus published articles before choosing the flow.
- Publish only after explicit approval for the exact revision.
- Store remote article ID and URL; support safe retries.

### Milestone 5 — Quality, evaluation, and observability
- Add LangSmith tracing/evaluation or another suitable observability approach.
- Measure source quality, citation coverage, factual support, writing-style consistency, tool errors, latency, and cost.
- Build a small evaluation dataset of representative topics and expected quality criteria.
- Track regressions when prompts, models, or workflow steps change.

### Milestone 6 — Advanced agents (optional)
- Consider specialized research, writing, and diagram agents only if the single-workflow design becomes difficult to maintain or parallel research provides a measurable benefit.
- Consider LangGraph subgraphs, routing, or delegation where justified.
- Consider Deep Agents if the application needs richer planning, filesystem/context management, and task delegation.
- Compare complexity, cost, latency, and reliability before adding these abstractions.

## 7. Candidate Architecture

Treat this as a proposal to validate against the existing repository, not a fixed requirement.

### Frontend
- Existing website framework if suitable; otherwise Next.js/TypeScript dashboard.
- Task creation form, progress view, article editor/preview, sources panel, diagram preview, review actions, and publication status.

### Application/API layer
- Reuse the existing backend if practical.
- If the project already uses NestJS, it may own authentication, task APIs, and publication adapters.
- Keep AI-specific logic in Python if that makes LangChain/LangGraph integration simpler, but avoid adding a separate service unless the benefits justify the operational cost.

### AI/workflow layer
- Python
- LangChain for model interfaces, prompts, tools, structured output, retrieval, and agent building blocks.
- LangGraph for explicit stateful workflow orchestration, checkpoints, revision paths, and human review.
- LangSmith or equivalent for tracing and evaluation.

### Storage
- PostgreSQL for tasks, article revisions, source metadata, approvals, and publishing records.
- pgvector only when semantic retrieval over existing articles/notes is introduced.
- S3 or an equivalent object store for diagram files and generated assets if needed.
- Use persistent LangGraph checkpoint storage in production. Do not rely on in-memory state for workflows that must survive restarts or wait for review.

### Integrations
- Web search/page extraction provider selected after comparing reliability, cost, and licensing.
- diagrams.net/draw.io XML for editable diagrams.
- Sanity client/API, using the actual project schema and current publishing model.
- DEV Community API, using current documentation and supported article states.

### Important architecture choice
Do not automatically add NestJS, FastAPI, PostgreSQL, pgvector, Redis, S3, LangGraph, LangSmith, and Deep Agents all at once. Choose only what the MVP needs and introduce each component when a requirement justifies it.

## 8. Data Model (Initial Proposal)

Ask the planning assistant to refine this after inspecting the current database and Sanity schema.

### WritingTask
- `id`
- `topic`
- `requirements`
- `audience`
- `language`
- `publication_targets`
- `status`
- `created_at`
- `updated_at`

### ArticleRevision
- `id`
- `task_id`
- `revision_number`
- `title`
- `slug`
- `markdown`
- `content_hash`
- `created_at`
- `created_by` (AI or owner)
- `approved_at` (nullable)

### ResearchSource
- `id`
- `task_id`
- `url`
- `canonical_url` (nullable)
- `title`
- `publisher` (nullable)
- `retrieved_at`
- `published_at` (nullable)
- `research_notes`
- `supporting_claims` (optional structured data)

### DiagramAsset
- `id`
- `task_id`
- `article_revision_id`
- `diagram_type`
- `source_xml_location` or stored XML
- `rendered_asset_location` (nullable)
- `validation_status`
- `created_at`

### Approval
- `id`
- `article_revision_id`
- `content_hash`
- `destination`
- `decision` (approved/rejected/revision_requested)
- `feedback` (nullable)
- `reviewed_at`
- `reviewer_id`

### Publication
- `id`
- `article_revision_id`
- `destination`
- `remote_document_id` (nullable)
- `remote_url` (nullable)
- `status`
- `attempt_count`
- `last_error` (nullable)
- `published_at` (nullable)

Use migrations and appropriate indexes. Avoid storing secrets in these records.

## 9. Workflow State and Statuses

Possible task statuses:

- `queued`
- `researching`
- `outlining`
- `drafting`
- `generating_diagram`
- `validating`
- `awaiting_review`
- `revision_requested`
- `approved`
- `publishing`
- `published`
- `partially_published`
- `failed`
- `rejected`

Define allowed state transitions explicitly. Enforce important transitions server-side rather than relying solely on model-generated decisions.

Keep workflow state distinct from durable business records. The article revision, approval, and publication history should remain queryable even if workflow execution fails.

## 10. Security and Reliability Requirements

- Never expose publishing tokens or search-provider credentials to the browser.
- Do not place secrets in prompts, model-visible state, traces, or logs.
- Use least-privilege API credentials where supported.
- Treat retrieved webpages, documents, and code as untrusted input; defend against prompt injection.
- Validate tool inputs and structured model outputs with schemas.
- Sanitize rendered Markdown/HTML and validate uploaded/generated files.
- Restrict allowed publication destinations and verify ownership/permissions.
- Enforce the human approval gate in the publishing service.
- Bind approval to the exact content hash/revision and destination.
- Invalidate approval when the approved content changes.
- Add timeouts, bounded retries, error reporting, and idempotent publication behavior.
- Avoid infinite agent loops and set maximum research/revision/tool-call budgets.
- Log enough for debugging without storing secrets or unnecessary sensitive data.
- Make failed tasks recoverable and show useful errors in the dashboard.

## 11. Evaluation Criteria

Define measurable acceptance criteria for each milestone. Suggested criteria:

### Research
- Important factual claims have supporting sources.
- Source links are retained and visible in the review interface.
- The system distinguishes unsupported claims from verified claims.
- Source quality can be inspected by the owner.

### Writing
- Output is valid Markdown.
- Required sections and requested technical depth are present.
- Code examples are syntactically plausible and tested where feasible.
- Style matches the configured preferences and relevant examples.
- Revisions address reviewer feedback without unnecessarily changing unrelated sections.

### Diagrams
- XML opens in diagrams.net/draw.io.
- Nodes and edges match the structured specification.
- Exported SVG/PNG is legible and can be embedded in the target publishing platform.
- The editable source is preserved.

### Review and publishing
- No article can be published without explicit approval.
- Approval is bound to the exact revision and destination.
- A content change after approval requires a new approval.
- Retries do not create duplicates when the destination supports safe deduplication.
- Publishing outcomes and remote URLs are recorded.

### Operations
- Workflow progress and failures are visible.
- A paused review workflow can resume after a service restart when persistent checkpointing is configured.
- Model/tool usage, latency, and cost can be inspected.

## 12. Questions for the Planning Assistant to Resolve

Before producing an implementation plan, inspect the available repository and identify:

1. What framework and content source does the existing personal website use?
2. Are blog posts currently stored in Sanity, Markdown/MDX, or another source?
3. What Sanity schemas, datasets, and draft/publishing conventions already exist?
4. Is there an existing backend, database, authentication, deployment pipeline, or object storage that should be reused?
5. Should the AI writing dashboard live inside the existing website, in a protected route, or as a separate internal application?
6. Which web-search and page-extraction providers are suitable, including pricing, limits, and licensing?
7. What is the most reliable way to produce and validate draw.io XML and export SVG/PNG?
8. What are the current DEV Community API capabilities and constraints for drafts and publication?
9. How should long-running workflows be deployed, resumed, and monitored in the existing infrastructure?
10. Which components can be postponed to keep the MVP small?

Do not invent repository details. If the repository or credentials are unavailable, list the assumptions and the information needed from the owner.

## 13. Requested Output from Gemini

Produce a detailed, implementation-ready plan with:

1. **Repository and current-site assessment** — existing stack, blog storage, relevant files, schemas, and deployment constraints.
2. **Recommended architecture** — component responsibilities and a diagram; justify each component and identify what not to add yet.
3. **Phased implementation plan** — MVP first, then style retrieval, diagrams, DEV publishing, evaluation, and optional advanced agents.
4. **Task breakdown** — ordered engineering tasks with dependencies and clear deliverables.
5. **API contracts** — endpoints, request/response examples, authorization, and error behavior.
6. **Database/schema changes** — tables/documents, relationships, indexes, migrations, and revision/approval strategy.
7. **LangGraph workflow design** — state schema, nodes, edges, conditional routing, checkpointing, interrupts, resume behavior, and failure paths.
8. **Tool specifications** — web search, page extraction, article retrieval, diagram generation/validation, and publishing adapters.
9. **Human-review UX** — draft editor, sources panel, diagram preview, revision feedback, approval by revision and destination.
10. **Security plan** — secrets, prompt injection, output validation, permissions, and the enforced publication gate.
11. **Testing plan** — unit, integration, workflow-resumption, API-mocking, publishing-safety, and evaluation tests.
12. **Deployment and observability** — environment variables, migrations, persistent checkpoint storage, logs/traces, alerts, and rollback.
13. **Acceptance criteria** — objective checks for each milestone.
14. **Risks and alternatives** — complexity, cost, latency, API limitations, licensing, and vendor lock-in.
15. **Learning map** — which LangChain, LangGraph, LangSmith, and optional Deep Agents concepts are learned in each phase.

Prioritize a small, reliable MVP. Do not start with multi-agent orchestration or Deep Agents unless the repository assessment identifies a concrete need. Separate confirmed facts from assumptions, and consult current official documentation for external APIs and framework behavior.
"""

path = Path("/mnt/data/personal_ai_technical_writer_project_brief.md")
path.write_text(content, encoding="utf-8")
print(f"Created: {path}")
