# Epic 10 — Diagram Quality: draw.io-Native Rendering & Visual Review

| | |
|---|---|
| **Milestone** | M3.1 (follow-up to Epic 7) |
| **Depends on** | Epic 7 (diagram pipeline), Epic 9 (eval dataset, LangSmith metadata) |
| **Source** | [`../../note.md`](../../note.md), lessons from building the Memory Up DevOps diagrams with the official draw.io skill |
| **Status** | Implemented 2026-11-05: awaiting owner review (parity sign-off pending) |

## Goal

Make the diagram readers see the **same** diagram the owner edits. Then make that diagram good enough to publish without hand fixes:

1. Render the published SVG/PNG from the `.drawio` file with **draw.io itself**, so real AWS/GCP/K8s/GitHub stencils appear on the blog and the exported image opens as an editable diagram.
2. Stop guessing shape names: every icon style is checked against draw.io's shape index.
3. Encode the layout fixes that worked by hand.
4. Add a **look-at-it-and-fix-it loop**: a vision model reviews the rendered PNG against a fixed checklist and feeds issues back.
5. Make diagram quality measurable in evals.

## Context (confirmed from the code, 2026-11-05)

| Area | Today | Problem |
|---|---|---|
| draw.io branch of `GenerateDiagramUsecase` | `build_diagram()` → `.drawio` XML **and** a Python SVG from `svg_renderer.py`; the PNG comes from `/render/png` (Chromium screenshots that SVG) | The published image uses hand-drawn glyphs from `icons.py`, not the `mxgraph.aws4.*` stencils in the `.drawio` file. Readers never see the real one. |
| `renderer/server.js` `/render/drawio` | Regex XML → SVG (`drawioXmlToSvg`, `getAwsIconInfo`, `renderAwsIconSvg`) | Can't render stencils. Used only by **Replace by upload** (`diagram_asset_usecases.py:129`), so uploaded edits publish badly too. |
| `renderer/Dockerfile` | `FROM minlag/mermaid-cli:latest` | Unpinned base image, and no draw.io CLI. |
| `icons.py` | 35 hand-written keys, AWS + generics; ALB/NAT/IGW wrapped in `resourceIcon` | Names are not verified against draw.io. Some resource icons may render wrong or blank. |
| `geometry.py` (~1,100 lines) | Deterministic layout + orthogonal routing | Known by-hand failures: labels on edges, edges along container borders, merged edges, edges crossing unrelated groups. |
| Evals | `diagram_valid` (0/1 on `validation_status`) | Says nothing about what the diagram looks like. |

Tooling for the **coding agent** (not the runtime) is already installed: the `drawio` skill, with `~/.agents/skills/drawio/scripts/find-shapes.js` and its XML rules. Use it while implementing these stories.

## In scope
- draw.io desktop CLI in the `renderer` container, and publishing from its output.
- Retiring the custom SVG path once it reaches parity.
- Shape-index validation and a generated icon catalogue (AWS, GCP, Kubernetes, GitHub).
- Layout rules in `geometry.py` / `drawio_generator.py`.
- A vision review node with bounded repair rounds.
- Diagram-focused eval cases and a visual-quality evaluator.

## Out of scope
- Azure and Cisco icon families. The catalogue script makes them a config change later.
- Replacing `geometry.py` for architecture diagrams. The ELK A/B in S9 covers flowcharts only.
- New diagram types.

---

## Target pipeline

```mermaid
flowchart LR
    SP[LLM → DiagramSpec] --> V{validate spec<br/>+ icon keys}
    V --> G[geometry.py<br/>+ layout rules]
    G --> X[.drawio XML]
    X --> R[renderer: drawio CLI<br/>SVG + PNG, XML embedded]
    R --> VR{vision review<br/>checklist}
    VR -- "issues, round < 2" --> SP
    VR -- ok / max rounds --> A[(diagram_assets<br/>+ review result)]
```

---

## Stories

### E10-S1 — draw.io CLI in the renderer container
**As** a developer, **I want** the renderer to export `.drawio` files with draw.io itself, **so that** published images use real stencils and match the editor exactly.

**Acceptance criteria**
- [ ] A spike compares two options and records the decision in this doc:
  - **A:** install the pinned draw.io desktop `.deb` + `xvfb` into the renderer image and run `xvfb-run -a drawio … --no-sandbox --disable-gpu`.
  - **B:** a separate pinned headless image (e.g. `rlespinasse/drawio-desktop-headless:<version>`) behind the same HTTP wrapper.
  - Compare image size, cold-start time and render time for `assets/samples/architecture.drawio`.
- [ ] Every image and package is pinned to a version, never `latest`. This includes replacing `minlag/mermaid-cli:latest`.
- [ ] `POST /render/drawio` runs the CLI and returns both outputs, with the diagram XML embedded (`-e`):
  - SVG: `drawio -x -f svg -e -b 10`
  - PNG at 2×: `drawio -x -f png -e -b 10 -s 2`
- [ ] The existing limits still apply: 30 s timeout, at most 2 concurrent renders, output ≤ 2 MB, SVG sanitised. A CLI failure returns a structured error, not a 500 with a stack trace.
- [ ] `GET /health` fails when the `drawio` binary is missing or can't start.
- [ ] `drawioXmlToSvg`, `getAwsIconInfo` and `renderAwsIconSvg` are deleted from `server.js`.
- [ ] Manual check: the exported SVG **and** PNG of the sample file open in diagrams.net as editable diagrams, with AWS icons drawn (not grey boxes).

**Size:** 5

---

### E10-S2 — Publish from the draw.io render; retire the custom SVG path
**As** the owner, **I want** the blog to show the draw.io render of the diagram, **so that** what I approve, what I edit and what readers see are the same picture.

**Acceptance criteria**
- [ ] In `GenerateDiagramUsecase`, the draw.io branch becomes geometry → `.drawio` XML → `renderer.render_drawio()` → store SVG + PNG. This applies to flowchart, architecture **and** sequence diagrams. **Replace by upload** uses the same path.
- [ ] `sha256` and the revision `content_hash` are computed from the draw.io-rendered SVG.
- [ ] Labels survive publishing. draw.io SVGs draw HTML labels inside `<foreignObject>`. Either `svg_sanitizer` allows `foreignObject` with XHTML content only (still no scripts, `on*` attributes or external `href`), or the PNG is published where SVG text would break. Check the result on the site preview and in the Dev.to render (Epic 8).
- [ ] **Parity gate before deleting anything:** render every diagram from the eval set (S8) through both paths and put the images side by side in `pdm/epic10_diagram_quality/parity/`. The owner signs off.
- [ ] After sign-off, delete `svg_renderer.py`, the glyphs in `icons.py`, `diagram_builder`'s SVG output and `/render/png` (if Mermaid doesn't need it). Move the palette constants that `drawio_generator.py` imports from `svg_renderer` into their own module.
- [ ] If the renderer is down, the existing graceful failure still applies: the article continues and an issue is flagged.
- [ ] The Diagrams tab hint (E7-S7) says the downloaded `.svg`/`.png` open directly in diagrams.net.

**Size:** 5

---

### E10-S3 — Validate every shape name against draw.io's index
**As** a developer, **I want** a test that fails on any `mxgraph.*` name draw.io doesn't know, **so that** guessed shapes never reach a published diagram.

**Acceptance criteria**
- [ ] `make diagrams-shape-index` downloads `search-index.json` from `jgraph/drawio-mcp` **pinned to a commit SHA**, not `@main`, into a checked-in fixture. Tests run offline.
- [ ] `api/tests/unit/diagrams/test_icons_exist.py` asserts that every shape and `resIcon` name produced by `resolve_icon` for every catalogue key exists in the index.
- [ ] Icon styles follow the two AWS patterns, using the style string the index returns:
  - **service icons** (EC2, EKS, ECR, S3, Route 53, IAM, …): `shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.<name>;fillColor=<category>;strokeColor=#ffffff;`
  - **resource icons** (ALB, NLB, NAT Gateway, Internet Gateway, Parameter Store, Users, …): `shape=mxgraph.aws4.<name>;fillColor=<colour>;strokeColor=none;`
- [ ] ALB, NAT and IGW, which are wrapped in `resourceIcon` today, are fixed. Each changed icon is rendered once through S1 and checked visually.
- [ ] The test also handles index entries that have no `mxgraph.*` name. Some GCP icons are `shape=image;image=data:image/svg+xml,…`, and for those the test checks that the catalogue style matches an index entry exactly.

**Size:** 2

---

### E10-S4 — Generate the icon catalogue from the index; add GCP, Kubernetes and GitHub
**As** the owner, **I want** the agent to use GCP, Kubernetes and GitHub icons as well as AWS, **so that** cloud, DevOps and platform diagrams look like the ones I draw by hand.

**Acceptance criteria**
- [ ] A script (`scripts/build_icon_catalogue.py`) reads the pinned index and an allowlist of keys, and writes a JSON catalogue: `key → {style, family, default_label}`. `icons.py` loads the catalogue instead of hard-coding styles.
- [ ] Keys are namespaced by family:
  - `aws:*`, e.g. `aws:eks`, `aws:alb`
  - `gcp:*`, e.g. `gcp:gke`, `gcp:cloud_run`, `gcp:compute_engine`, `gcp:cloud_sql`, `gcp:cloud_storage`, `gcp:bigquery`, `gcp:pubsub`, `gcp:load_balancing`, `gcp:iam`, `gcp:cloud_functions`
  - `k8s:*`, using `mxgraph.kubernetes.icon2;prIcon=…` for pod, deploy, svc, ing, job, secret and ns
  - `gh:github` (`mxgraph.weblogos.github`)
  - existing generic keys
- [ ] GCP icons are chosen from the index in a fixed order: `mxgraph.gcp3.<name>` stencils first, then `mxgraph.gcp2.<name>`, then the index's `shape=image` entry. The index was checked on 2026-11-05:
  - `gcp3` has GKE (`gke`), Cloud Run (`cloudrun`), Compute Engine (`computeengine`), Cloud SQL (`cloudsql`), Cloud Storage (`cloud_storage`) and BigQuery (`bigquery`).
  - Pub/Sub, Load Balancing, IAM and Cloud Functions are **not** in `gcp3`, so they need the fallback.
  - The source each key resolved from is recorded in the catalogue.
- [ ] GCP icons share one colour (`#4285f4`) for a consistent look. GCP group containers (Project, Region, VPC network) get styles in `group_styles.py`, next to the AWS ones, so that `cloud → region → vpc` nesting works for GCP specs too.
- [ ] One spec does not mix AWS and GCP container styles: the group style family follows the majority of icon keys in the spec.
- [ ] The 35 existing keys keep working as aliases, so old specs and stored assets still resolve.
- [ ] The diagram prompt lists **keys only**, never styles, and `resolve_icon` does the lookup. The key list adds no more than ~300 tokens to the prompt.
- [ ] `spec_validator` returns a repairable error for unknown icon keys, which goes into the existing repair loop. A key that still fails falls back to the node's `kind` shape and a warning is logged.
- [ ] S3's test covers every generated entry. Each GCP key is rendered once through S1 and checked visually (no blank or grey icons).

**Size:** 5

---

### E10-S5 — Layout rules: labels, ports and edge hygiene
**As** the owner, **I want** labels and edges that never sit on top of each other, **so that** I don't have to drag things around before publishing.

**Acceptance criteria**
- [ ] Icon nodes with an outgoing edge from the bottom get their label on the side: `labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;`.
- [ ] When two or more edges leave one node toward targets that are close together, each edge gets its own explicit port (`exitX/exitY`, `entryX/entryY`), so they don't merge into one line.
- [ ] Every edge has `labelBackgroundColor=default`.
- [ ] An edge's `parent` is the innermost container holding both ends, with coordinates relative to that container.
- [ ] XML hygiene is enforced in `drawio_validator`:
  - no XML comments
  - unique ids
  - `& < > "` escaped in attributes
  - HTML labels double-escaped (`&amp;lt;sha&amp;gt;` shows `<sha>`)
- [ ] A geometry lint, `layout_lint.py` (pure Python, run on the computed geometry), detects text/edge overlap, edges through unrelated nodes and two edges sharing a segment. The geometry snapshot tests assert zero lint findings on the fixture specs.

**Size:** 3

---

### E10-S6 — Layout rules: placement, container borders, legend
**As** the owner, **I want** architecture diagrams arranged the way I would arrange them, **so that** long edges stay short and readable.

**Acceptance criteria**
- [ ] **Container borders:** no edge segment runs along or within 8 px of a group border. When a segment would fall between nested borders (e.g. `VPC | Region | Cloud`), waypoints (`<Array as="points">`) push it outside the containers.
- [ ] **External systems** (`kind: external`, or nodes outside every group) are placed on the side their edges go to, e.g. DB/ACME to the right next to the NAT gateway, and GitHub to the left next to Argo CD.
- [ ] **Regional services** (top-level nodes inside a region group that aren't in a VPC) are placed in a row along the bottom of the region, not a side column.
- [ ] **Edge meaning:** solid means data path and dashed means control/automation. When a diagram uses both, a small legend is added automatically. The diagram prompt explains this convention.
- [ ] The layout lint (S5) adds an "edge on container border" check. The fixture for the Memory Up–style EKS architecture produces zero findings.
- [ ] Determinism is kept: the same spec gives the same XML (existing snapshot tests).

**Size:** 5

---

### E10-S7 — Vision review node with bounded repair
**As** the owner, **I want** the agent to look at its rendered diagram and fix obvious problems, **so that** the diagram I review is already clean.

**Acceptance criteria**
- [ ] A `review_diagram` step runs after rendering, for draw.io and Mermaid alike. It sends the PNG to a vision-capable model (new `ModelRole.VISION`, Gemini by default, configurable) with this checklist, and gets back Pydantic-validated JSON:
  1. Any text overlapping another text, icon or edge?
  2. Any edge passing through a box/icon it doesn't connect to?
  3. Any edge drawn along a container border, or two edges sharing one line?
  4. Any text cut off or overflowing its shape?
  5. Any edge label far from its edge, or ambiguous about which edge it belongs to?
  6. Any icon rendered blank or as a grey box?
- [ ] Output schema: `{passed: bool, issues: [{check: 1-6, severity: minor|major, description, labels_involved[]}]}`.
- [ ] When there are major issues, the issues are formatted into the existing `feedback` argument of `diagram_messages`, and the spec is regenerated. There are **at most 2 review rounds**. The version with the fewest major issues is kept, not just the last one.
- [ ] The S5 lint findings are added to the feedback too, so the model gets precise facts as well as the vision summary.
- [ ] The final review result and round count are stored on `diagram_assets` (Alembic migration `0009`, `review` json + `review_rounds`). The Diagrams tab shows remaining issues next to the validation status.
- [ ] LangSmith run metadata includes `diagram_review_passed`, `diagram_review_major_issues` and `diagram_review_rounds`.
- [ ] Review calls count toward the task's token/cost budget (`run_usage`). `DIAGRAM_VISUAL_REVIEW=false` turns the step off. If the review model fails, the diagram is kept and the review is marked `skipped`.

**Size:** 5

---

### E10-S8 — Diagram eval cases & visual-quality evaluator
**As** the owner, **I want** diagram quality scored in evals, **so that** I can see whether a prompt or layout change made diagrams better or worse.

**Acceptance criteria**
- [ ] `api/evals/dataset.yaml` gets four diagram-focused examples with `reference.diagram_type`:
  - an **AWS architecture** diagram (AWS EKS + Argo CD + GitHub, Memory Up style)
  - a **GCP architecture** diagram (GKE + Cloud Run + Cloud SQL + Cloud Storage + Pub/Sub)
  - a **flowchart**
  - a **sequence** diagram
- [ ] A new evaluator, `diagram_visual_quality`, reuses the S7 reviewer prompt and scores `1 − (0.25 × major + 0.05 × minor)`, floored at 0. A second evaluator, `diagram_icons_resolved`, is the share of icon nodes with a catalogue hit.
- [ ] Both evaluators are added to `compare_experiments.py` with weights next to `diagram_valid`.
- [ ] A **baseline** experiment runs on the pre-Epic-10 commit before S2 merges, and its result is recorded here. Each later story records its delta.

**Size:** 3

---

### E10-S9 — (Optional) A/B test draw.io's ELK layout for flowcharts
**As** a developer, **I want** to know whether draw.io's own layout beats `geometry.py` for flowcharts, **so that** we keep only the layout code that earns its place.

**Acceptance criteria**
- [ ] The renderer supports `layout: verticalFlow | horizontalFlow | libavoid` (`drawio -x -f xml --layout …`).
- [ ] An experiment runs the flowchart eval cases with `geometry.py`, with ELK, and with `geometry.py` + `libavoid` re-routing, scored with `diagram_visual_quality`.
- [ ] Decision recorded here: adopt per diagram type or drop. Architecture diagrams stay on `geometry.py` either way, because group nesting matters there.

**Size:** 3

---

## Suggested order

```text
S8 (eval cases + baseline only) ─┐
S1 ──► S2 ──► S3 ──► S4 ──► S5 ──► S6 ──► S7 ──► S8 (finish evaluator wiring) ──► S9 (optional)
```

S1 and S2 have the biggest impact: they alone put real stencils on the blog. S8's dataset entries and baseline run should land first, so every later story can show its effect.

**Total:** 36 points (33 without S9).

## Definition of done (epic)
- For the four diagram eval cases, the published image is the draw.io render, and it opens as an editable diagram in diagrams.net.
- Every icon in the catalogue exists in the pinned shape index (test green). None renders blank.
- `diagram_visual_quality` averages at least 0.8 on the eval set and beats the baseline.
- `svg_renderer.py`, the glyph table and the regex `drawioXmlToSvg` are gone.

## Learning map
| Tool | Concepts |
|---|---|
| LangChain | Multimodal (image) input, structured output from a vision model |
| LangGraph | A bounded critique → repair loop, keeping the best candidate rather than the last one |
| LangSmith | Run metadata as a quality signal, comparing experiments against a baseline |

---

## Implementation notes (delivered 2026-11-05)

| Story | Where | Notes |
|---|---|---|
| E10-S1 | `renderer/Dockerfile`, `renderer/server.js`, `renderer/entrypoint.sh`, `docker-compose.yml` | **Spike decision: one Debian image (a variant of option A).** Option A as written was not possible: the old base `minlag/mermaid-cli` is Alpine, so the draw.io `.deb` cannot be installed in it. Option B would need its own HTTP wrapper in a second container. The renderer is now `node:22.20.0-bookworm-slim` with: draw.io desktop **32.4.1** (`.deb` checksum-verified), Debian's Chromium, `@mermaid-js/mermaid-cli@11.17.1` and `puppeteer@24.43.1`, all pinned. One shared Xvfb is started by the entrypoint, and the service runs as a non-root user. **Measured:** the image is **2.54 GB** (above the ~1.5 GB estimate; Chromium and Electron are both inside). Health turns 200 about **9 s** after start. A render (SVG + 2× PNG, two Electron runs) takes **4–9 s**. **Export flags:** `-x -e -b 10 --theme light`; SVG adds `--embed-svg-images --embed-svg-fonts false`, PNG adds `-s 2`. `--theme light` is needed because the default `auto` wraps colours in CSS `light-dark()`, which turns our dark diagrams light for readers in dark mode. Not embedding fonts cuts the SVG ~7× (EKS: 460 → 109 KB) and labels still render. `/health` only returns 200 after a real smoke export, and the Compose `start_period` is 60 s with `shm_size: 256m`. Errors are structured: `MISSING_XML` 400, `DRAWIO_RENDER_ERROR` 422, `OUTPUT_TOO_LARGE` 422. `drawioXmlToSvg`, the AWS-icon helpers and `/render/png` are deleted. **Verified:** the published SVG **and** PNG of `three-tier` convert back to the full diagram with the draw.io CLI (18/18 cells). |
| E10-S2 | `usecases/generate_diagram_usecase.py`, `usecases/diagram_asset_usecases.py`, `domain/diagram_builder.py`, `domain/palette.py`, adapter | The draw.io branch is now geometry → `.drawio` → `render_drawio()` → SVG + PNG. This covers flowchart, architecture and sequence diagrams, plus **Switch format** and **Replace by upload**. `sha256` is the hash of the API-sanitised SVG we store. `render_drawio` no longer returns a placeholder: if the renderer is down it raises, the node emits `diagram_failed`, and the article continues. Upload and switch return a 400 that says so. **Labels:** draw.io uses `<foreignObject>`, which both sanitisers already keep. A screenshot of the sanitised SVG inside `<img>` in Chromium with `prefers-color-scheme: dark` shows every label and the dark background. *Not checked:* the live site and Dev.to themselves. **Parity gate:** [`parity/README.md`](parity/README.md) compares legacy and draw.io renders for 6 reference diagrams. **Signed off 2026-11-05**; `svg_renderer.py`, the glyph table, `legacy_svg()` and the parity script were then deleted. The palette moved to `palette.py`. The UI tip now says the downloaded `.svg`/`.png` open in diagrams.net. |
| E10-S3 | `catalogue/icon_allowlist.json`, `scripts/build_icon_catalogue.py`, `tests/fixtures/drawio_shape_index.json.gz`, `tests/unit/diagrams/test_icons_exist.py` | The index is pinned to `jgraph/drawio-mcp@312d8062`. A **53 KB derived fixture** is checked in instead of the 4.7 MB index. It holds every shape, `resIcon` and `prIcon` name, plus hashes of the `shape=image` styles, and is byte-identical on every rebuild. `make diagrams-icons` rebuilds it (`REFRESH=1` re-downloads). **The test found a real bug:** `aws:alb` used `resIcon=mxgraph.aws4.application_load_balancer`, which is not a valid resIcon. ALB/NLB/NAT/IGW/Parameter Store/User(s) are now standalone stencils (`strokeColor=none`) and were checked visually. |
| E10-S4 | same + `domain/icons.py`, `domain/group_styles.py`, `prompts/diagram.py` (`diagram-v2`) | **73 icons:** 35 AWS, 14 GCP, 13 Kubernetes, GitHub, and 10 generic. Every old key still resolves. **GCP sources:** `gcp3` stencils for GKE, Cloud Run, Compute Engine, Cloud SQL, Cloud Storage, BigQuery, Spanner, AlloyDB, Vertex AI and Apigee. Load Balancing falls back to `gcp2`. Pub/Sub, IAM and Cloud Functions use the index's `shape=image` entries, which are embedded `data:` SVGs only, never remote. All are `#4285F4`. The prompt lists keys only (~180 tokens). The same label (e.g. "Load Balancer") resolves to the GCP icon in a GCP diagram and the AWS one in an AWS diagram. **GCP containers** (Google Cloud, Project, Region, Zone, VPC network, Subnet) and **K8s containers** (cluster, namespace) are plain styled frames, because the index has no GCP boundary stencils. One diagram uses one cloud's frame styles (`DiagramGeometry.family`). All 73 icons rendered in one grid ([`parity/icon-catalogue.png`](parity/icon-catalogue.png)): none blank or grey. The `gcp2` Load Balancing icon is the weakest-looking one. |
| E10-S5 | `domain/layout_lint.py`, `geometry.py`, `drawio_generator.py`, `drawio_validator.py` | **Lint:** checks text overlap, edges through nodes, edges along borders, shared lines, and label-side exits. **Router:** a re-route pass for edges that still share a line. Edge labels sitting on another edge now cost 400. Edges are parented to the innermost common container, with relative waypoints. Labels now carry an `as="offset"` point. *Found in the visual check:* draw.io was drawing every label on its line even when the layout had placed it beside the line. The validator now rejects comments and unescaped label markup (`strict=False` for owner uploads). **Deviation:** labels use the explicit background colour, not `labelBackgroundColor=default`, because draw.io's CLI renders `default` as **white**. The sequence diagram had exactly that bug (white boxes, unreadable). A test now checks every labelled edge. |
| E10-S6 | `geometry.py` | **Borders:** routing lines within 8 px of a group border are dropped (except port stubs), and running alongside a border costs 12×. Root cause: the midpoint between `border±10` *was* the border. **Services row:** the bottom row takes only nodes whose neighbours all sit in nested frames (S3/ECR/Parameter Store do; a GCP load balancer or Cloud Run API on the main flow doesn't). Nodes linked to the row move their label to the top in LR layouts. **External systems** linked to one frame go on the side their neighbours are on (DB/ACME next to the NAT). **Legend** appears when solid and dashed edges are both used. Node clearance went from 14 to 18 px after the real review flagged a line running 13 px from an icon. EKS width went from 2173 to 1590 px. |
| E10-S7 | `prompts/diagram_review.py`, `schemas/diagram_review.py`, `GenerateDiagramUsecase`, migration `0009`, `DiagramsPanel.tsx` | `ModelRole.VISION` (`LLM_VISION_MODEL`, falling back to the default model). **Loop:** each round re-generates the spec with the vision issues + lint findings as feedback, at most `DIAGRAM_REVIEW_MAX_ROUNDS=2` extra rounds. The winner has the fewest major issues (vision + lint), then fewest minor, then the later round. `diagram_assets.review` (json) and `review_rounds` come from migration `0009`. The Diagrams tab shows the status, up to 5 remaining issues and the round count. Review calls get the workflow callbacks, so they are traced and counted in `run_usage`. A `diagram_review_summary` run carries `diagram_review_passed/major/minor/rounds` as LangSmith metadata. `DIAGRAM_VISUAL_REVIEW=false` turns it off. A model error means `status=skipped` and the diagram is kept. **Real check with `gemini-3.8-flash`:** valid structured output in 23–28 s per call. It flagged one major issue on EKS (the line hugging the IGW); after the clearance change, EKS and GCP both pass with 0/0. |
| E10-S8 | `evals/dataset.yaml` (eval-13…16), `evaluation/domain/diagram_evaluators.py`, `run_eval.py`, `compare_experiments.py`, `tests/unit/test_run_eval.py` | Four cases: AWS EKS GitOps, GCP serverless, a flowchart, and a webhook sequence. **`diagram_visual_quality`** uses the stored review, or runs the same reviewer on the PNG when there is none, so older runs can be scored. **`diagram_icons_resolved`** is the share of icon keys in the catalogue. Both have thresholds in `compare_experiments.py`. `predict()` now passes `include_diagram`/`diagram_format` and returns `diagram_assets` (before this, `diagram_valid` never saw assets). **Fixed `run_eval.py` (broken since Epic 9):** it failed at import (`ModelFactory`, `PageExtractor`, `TavilySearchProvider`, `ArticleFormat`, `TargetAudience` and the `judge_*` names don't exist), called `PromptRegistry` methods on the class, read nonexistent `config.*_model` fields, called async judges without awaiting, and passed `*args` evaluators that LangSmith 0.14 rejects. It now builds its dependencies like `src/main.py`, streams the graph like the runner (callbacks and task events), and wraps every evaluator in a LangSmith-compatible signature. `--limit` now also works on the LangSmith path. Unit tests cover task building for all 16 examples, LangSmith's own signature check on all 16 evaluators, and the sync/async wrapper. **Baseline:** not run yet (a full eval is many LLM calls per example); `make eval` now works. |
| E10-S9 | — | **Not done** (optional). Needs a working `make eval`. |

**Verification:**
- **382 unit tests pass** (258 before), including:
  - shape names against the index for all 73 icons
  - zero lint findings on 5 reference layouts
  - each lint check firing on a broken geometry
  - row, side-placement, legend and edge-parent rules
  - double escaping
  - the review loop with scripted models: repair, best-round choice, review disabled, model failure, renderer down, callbacks and metadata
  - both evaluators
- UI type check and lint pass (3 pre-existing warnings).
- Migration `0009` was only checked as offline SQL. **It hasn't run on a database**, and integration tests weren't run (no Postgres).
- **Real renders:** in a standalone `blog-agent-renderer:e10` container. The Compose stack was not rebuilt or started, and `.env` was not changed.


