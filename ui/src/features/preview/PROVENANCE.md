# Provenance of the site-accurate preview

The preview must render a draft exactly as https://leon-pham.vercel.app renders a post ("what I approve is
what readers see"). The code below is copied from `profile-ui` and should be re-synced whenever the site's
renderer changes.

| Dashboard file | Copied from (profile-ui) | Source commit |
|---|---|---|
| `normalize-markdown.ts` | `components/post/MarkdownComp.tsx` → `normalizeMarkdown` (verbatim) | `0ec342ef2ec133b78de9caa4e9e09399d9f6db9f` |
| `components/SitePreview.tsx` | `components/post/MarkdownComp.tsx` (plugins, component overrides) and `components/post/TracingBeamComp.tsx` (post header: H1 + 16:9 cover) | same |
| `components/MermaidDiagram.tsx` | `components/post/MermaidRenderer.tsx` (config, theme variables, inline styles) | same |
| `site-preview.css` | `app/globals.css` → `.prose-post` and `.katex-display` rules, site background (zinc-950) | same |

Same package versions as the site: `react-markdown` (10 here, 9 on the site — same output for this plugin set),
`remark-gfm` 4, `remark-math` 6, `rehype-raw` 7, `rehype-katex` 7, `rehype-slug` 6, `katex` 0.19, `prismjs` 1.30
(grammars: bash, java, javascript, json, markdown, python, typescript), `mermaid` 12.2.

## Deliberate differences

1. **Sanitisation.** The site renders raw HTML unsanitised. The preview runs `rehype-sanitize` (GitHub schema +
   math classes) between `rehype-raw` and `rehype-katex`, and shows a "Sanitised" badge when anything was
   removed — a sign the Markdown contains HTML the render contract does not allow.
2. **Mermaid `securityLevel: "strict"`** instead of `"loose"`: labels keep `<b>`/`<br/>`, but click handlers
   and scripts in model-written diagrams never run in the dashboard.
3. **Links** open in a new tab; in-page anchors scroll inside the preview instead of changing the dashboard URL.
4. **Tailwind v3 → v4.** The site's `.prose-post` rules win over utilities by specificity (v3); here they are
   unlayered CSS so they win over v4's layered utilities in the same way. v4's zinc palette is oklch and differs
   from v3's hex values by less than a visible step.
5. **Font.** The site loads Geist but never applies it (no `fontFamily` in `tailwind.config.ts`), so posts render
   in Tailwind v3's default system stack; the preview uses that stack too, at the site's 16px base size.
6. **Not ported:** the decorative `TracingBeam` scroll line and the "Back to blogs" link.
7. Raw-HTML `id`/`name` attributes get the sanitiser's `user-content-` prefix (heading ids from `rehype-slug`
   are unaffected, so TOC anchors match the site).

## Re-sync checklist

1. `git -C ../profile-ui log -1 --format=%H -- components/post app/globals.css` and compare with the commit above.
2. Diff the files listed in the table, port the changes, update the commit.
3. Open `/preview/fixtures` in the dashboard and a published post on the site side by side.
