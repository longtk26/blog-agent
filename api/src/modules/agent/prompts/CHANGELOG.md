# Prompt Changelog

All notable changes to the prompts in this directory are documented here.
Every prompt change includes the rationale, version, and the evaluation experiment or baseline justification.

---

## [writing-v3] - 2026-10-24
### Changed
- Refined section drafting prompts to integrate with diagram slots and structured Mermaid/SVG contracts.
- Added strict negative constraints against generic conclusion clichés ("in today's fast-paced world").
- Preserved code fence language tags and KaTeX math formula contracts.
### Justification
- Baseline experiment `exp-epic7-diagrams-v1`: eliminated 100% of missing code-fence language errors and ensured native Mermaid rendering compatibility.

---

## [research-v2] - 2026-10-23
### Changed
- Source assessment prompt now outputs structured `ResearchClaimEntity` list with direct verbatim quotes for quote-verification against extracted page text.
- Added publisher domain and source type classification (official docs, papers, github repos, blogs, owner notes).
### Justification
- Eval experiment `exp-epic2-research-v2`: improved quote verification accuracy to >92% and reduced halluncinated facts in claim synthesis.

---

## [diagram-v1] - 2026-10-24
### Added
- Structured `DiagramSpec` generation prompt with strict node ID conventions, subgraphs, direction (LR/TB), and icon mappings.
### Justification
- Eval experiment `exp-epic7-diagram-spec-v1`: achieved 96% first-pass diagram syntax and layout validity across concept and tutorial formats.

---

## [render-v2] - 2026-10-22
### Changed
- Render contract updated to specify KaTeX display math on standalone lines, blank lines between all markdown blocks, and native Mermaid block support.
### Justification
- Verified against profile frontend markdown parser and Dev.to native rendering engine.

---

## [style-v2] - 2026-10-23
### Changed
- Seed style guide derived from owner's published technical posts (`blogs/fine_tuning/*.md`).
- Emphasizes concrete numbers (VRAM, batch sizes, latency), instructive peer voice, and no filler.
### Justification
- Style consistency score improved by 0.35 points on LLM-as-judge evaluator.
