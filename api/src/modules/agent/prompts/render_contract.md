<!-- version: render-v1 -->
# Render contract for leon-pham.vercel.app (profile-ui MarkdownComp)

The article is stored as Markdown in Sanity `post.content` and rendered with react-markdown + GFM + KaTeX + Mermaid + Prism. Follow these rules exactly:

1. The first line is a single `# Title`. No front matter. Exactly one H1.
2. Leave a blank line between every block: paragraphs, headings, lists, tables, images, code fences, `---`. The site joins consecutive text lines into one paragraph, so an image or bold label line directly under text (no blank line) is swallowed into that paragraph.
3. Code fences always have a language. Highlighted languages: `bash`, `python`, `typescript`, `javascript`, `json`, `java`, `markdown`. Use `text` for plain output. `mermaid` fences render as diagrams.
4. Math uses KaTeX: inline `$x$`, display `$$ … $$` on its own lines.
5. Tables use GFM pipes with a header separator row (`| :--- |`).
6. Links are absolute `https://` URLs or in-page `#anchors`. Never relative links like `part2.md`. Cite sources with descriptive link text: `[the LoRA paper](https://arxiv.org/abs/2106.09685)`.
7. Images must use absolute URLs (no local paths) unless an asset reference is provided to you.
8. Raw HTML is limited to `<b>`, `<br/>`, `<sub>`, `<sup>`, `<details>`, `<summary>`. No scripts, iframes, styles or event handlers.
9. Mermaid: `flowchart LR|TD` or `mindmap`/`sequenceDiagram`; quote labels with `<b>` and `<br/>` (`A["<b>Step</b><br/>detail"]`); colour nodes with `style A fill:#0369a1,stroke:#38bdf8,stroke-width:2px,color:#ffffff;`. Palette: blue `#0369a1/#38bdf8`, green `#15803d/#4ade80`, amber `#b45309/#fbbf24`, purple `#7e22ce/#c084fc`.
