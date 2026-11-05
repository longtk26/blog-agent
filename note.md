# Note: improving the blog agent's diagrams

These notes come from building the Memory Up DevOps diagrams (`memory-up/docs/devops/diagrams/`) with the official draw.io skill, compared against how Epic 7 works here today.

## 0. Install the skill (for the coding agent, not the runtime)

```bash
npx skills add jgraph/drawio-mcp@drawio -g -y   # official skill from jgraph (draw.io's maker)
```

The skill teaches a *coding agent* (Claude Code, Codex, …) how to write `.drawio` XML, look up real shape names and export with the draw.io CLI. It does **not** change the LangGraph blog agent by itself. For that, port the ideas below into `api/src/modules/diagrams/` and `renderer/`.

Useful parts of the skill to reuse:
- `~/.agents/skills/drawio/scripts/find-shapes.js`: searches draw.io's shape index and prints exact `style` strings.
- Shape index (JSON): `https://cdn.jsdelivr.net/gh/jgraph/drawio-mcp@main/shape-search/search-index.json`.
- XML rules: `https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/xml-essentials.md`.

---

## 1. What the agent does today

| Step | Where | Notes |
|---|---|---|
| LLM → `DiagramSpec` (nodes, groups, edges, icon keys) | `agent/prompts/diagram.py`, `domain/schemas/diagram_spec.py` | Good: structured output, no raw XML from the LLM |
| Layout + orthogonal routing | `domain/geometry.py` (~1,100 lines) | Deterministic, one geometry for both outputs |
| `.drawio` file | `domain/drawio_generator.py` | Uses real `mxgraph.aws4.*` stencils |
| **Published image** | `domain/svg_renderer.py` + `icons.py` glyphs | **Hand-drawn simplified glyphs, not the draw.io stencils** |
| `/render/drawio` | `renderer/server.js` → `drawioXmlToSvg` | Regex-based XML → SVG; can't render stencils |
| Icons | `domain/icons.py` | 35 fixed keys, AWS-only plus generics |

**The main gap:** the blog shows a homemade SVG, while the real AWS-icon version exists only in the `.drawio` file. Readers never see the good one.

---

## 2. Improvements, highest impact first

### 2.1 Rasterise with draw.io itself

Render the published PNG/SVG from the `.drawio` file using **draw.io desktop's CLI** inside the `renderer` container:

```bash
drawio -x -f svg -e -b 10      -o out.drawio.svg in.drawio
drawio -x -f png -e -b 10 -s 2 -o out.drawio.png in.drawio
```

- Container options: install the drawio `.deb` + `xvfb` in `renderer/Dockerfile` and run with `xvfb-run -a drawio … --no-sandbox --disable-gpu`. Or use a headless image such as `rlespinasse/drawio-desktop-headless`, pinned to a version tag, never `latest`.
- `-e` embeds the diagram XML in the PNG/SVG, so the **published image opens as an editable diagram in draw.io**. You can drop the separate source-file step.
- Then `svg_renderer.py`, the glyphs in `icons.py`, and `drawioXmlToSvg` in `renderer/server.js` can be retired. Keep `svg_sanitizer` on the output.
- What you get: real AWS/K8s/GitHub icons, identical output in the editor and on the blog, and much less code to maintain.

### 2.2 Validate every shape name against draw.io's index

Never let a guessed `mxgraph.*` name through. Download `search-index.json` at build time and add a unit test:

```python
# api/tests/unit/diagrams/test_icons_exist.py
# for each IconSpec in ICONS: assert its shape/resIcon name exists in the index
```

Two kinds of AWS shapes behave differently. Copy the style the index returns instead of building it yourself:
- **Service icons** (EC2, EKS, ECR, S3, Route 53, IAM): `shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.<name>;fillColor=<category colour>;strokeColor=#ffffff;`
- **Resource icons** (ALB, NLB, NAT Gateway, Internet Gateway, Parameter Store, Users): standalone shapes, `shape=mxgraph.aws4.<name>;fillColor=<colour>;strokeColor=none;`.
  Today `icons.py` wraps ALB/NAT/IGW in `resourceIcon`. Render them once and check they look right.

### 2.3 Grow the icon catalogue from the index, not by hand

Generate `icons.py` (or a JSON catalogue) from the index with a script, and add other families too:
- Kubernetes: `mxgraph.kubernetes.icon2;prIcon=pod|ing|job|secret|ns|deploy|svc`
- GitHub: `mxgraph.weblogos.github`
- Azure: `azure2`
- GCP and Cisco also exist.

Keep the prompt short by listing only key names (`aws:eks`, `k8s:pod`, …) and resolving styles in code, as `resolve_icon` already does.

### 2.4 Add a visual review loop

My diagrams got good because I **looked at the rendered PNG and fixed what was wrong**. On the first render I found:
- labels on top of edges,
- a vertical edge running along three container borders,
- text overflowing its box,
- two edges merging into one another,
- an edge crossing an unrelated namespace.

Do the same in the graph:

```
spec → geometry → .drawio → render PNG → vision-model review (checklist below) → issues?
   └──────────── feedback (diagram_messages already has a `feedback` arg) ◄──────┘   max 2 rounds
```

Review checklist, which the vision model returns as JSON:
1. Any text overlapping another text, icon or edge?
2. Any edge passing through a box/icon it doesn't connect to?
3. Any edge drawn along a container border, or two edges sharing one line?
4. Any text cut off or overflowing its shape?
5. Any edge label far from its edge, or ambiguous about which edge it belongs to?
6. Any icon rendered blank or as a grey box (a wrong shape name)?

Log the review result as LangSmith metadata (Epic 9), so diagram quality becomes measurable in evals.

### 2.5 Layout techniques worth encoding in `geometry.py` / `drawio_generator.py`

These are the fixes that made the difference:
- **Move icon labels to the side** when edges leave from the bottom: `labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;`. Bottom labels on icons with outgoing bottom edges always collide.
- **Use explicit ports** (`exitX/exitY/entryX/entryY`) when two edges leave the same node toward targets that are close together. Otherwise they merge.
- **Add waypoints** (`<Array as="points"><mxPoint …/></Array>`) to push a segment **outside** nested containers. A segment halfway between `VPC | Region | Cloud` borders lands right on top of them.
- **Place external systems on the side their edges go to.** For example, DB and ACME on the right next to the NAT gateway, and GitHub on the left next to Argo CD.
- **Use a regional services row at the bottom** instead of a side column, so long edges stay short and vertical.
- **Solid edges are the data path, dashed edges are control/automation**, plus a small legend.
- **Set `labelBackgroundColor=default` on edges**, so labels stay readable where they cross borders.
- **Set the edge parent to the innermost container holding both ends.** Coordinates of children are relative to their container.
- **Avoid XML comments**, use unique ids, and escape `& < > "` inside attribute values. HTML labels are XML-escaped twice (`&amp;lt;sha&amp;gt;` to show `<sha>`).

### 2.6 Optional: let draw.io lay it out

For flowcharts, `drawio -x -f xml --layout verticalFlow|horizontalFlow -o out.drawio in.drawio` applies ELK. `--layout libavoid` reroutes edges around shapes without moving nodes. Worth A/B-testing in the eval set against `geometry.py` for flowcharts. Keep `geometry.py` for architecture diagrams, where group nesting matters.

---

## 3. Suggested order (fits Epic 7)

1. Renderer: draw.io CLI in the container, plus a `/render/drawio` that returns PNG and SVG with embedded XML.
2. Usecase: publish from the draw.io render, and delete the custom SVG path once it's at parity.
3. A unit test that every icon style exists in the shape index, then regenerate the catalogue with K8s and GitHub icons.
4. A vision review node with the checklist above, using the existing `feedback` argument and max 2 rounds.
5. Eval cases in `api/evals/dataset.yaml` for one architecture, one flowchart and one sequence diagram, scored on the checklist.
