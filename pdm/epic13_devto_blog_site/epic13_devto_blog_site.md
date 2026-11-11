# Epic 13 — Website Blog on DEV (profile-ui)

| | |
|---|---|
| **Milestone** | M3.2 |
| **Depends on** | Epic 8 (Dev.to publishing, canonical URLs), Epic 12 (S3 diagram URLs) |
| **Code** | `profile-ui/` (separate repo) |
| **Status** | Implemented 2026-11-11: awaiting owner review |

## Goal
https://leon-pham.vercel.app/blogs reads posts from DEV (dev.to) instead of Sanity, and shows DEV page views, reactions
and comments. The owner chose to **retire Sanity on the website only**: the Blog Agent's Sanity target, `/blog-manager` and
`/api/publish` (local tools) are untouched.

## Research answer (2026-11-11)
- `GET /api/articles/me/published` (needs `api-key`) returns `page_views_count`, `public_reactions_count`, `comments_count`,
  `reading_time_minutes`, `tag_list`, `canonical_url` **and `body_markdown`**: the whole blog comes from one call.
- `GET /api/comments?a_id=<id>` is public: a threaded tree with sanitised `body_html`.
- Without a key, the public `GET /api/articles?username=` gives everything except page views and bodies (bodies come from `/api/articles/{id}`).
- All 8 Sanity posts exist on DEV. Only the newest has a canonical URL on the site; the other 7 point at dev.to.

## What changed
| Area | Change |
|---|---|
| Data | `external/devto/` (`server-only`): `getPosts`, `getPost(slug)`, `getComments(id)`; fetch cache 10 min, tag `devto`; falls back to the public API (views hidden) when `DEV_TO_API_KEY` is missing; decodes DEV's HTML-escaped titles and descriptions; strips the Blog Agent's "Originally published at" footer |
| URLs | `/posts/[slug]` (was `[id]`). Slug = canonical slug when the canonical URL is on the site (so Blog Agent canonicals resolve), else DEV's slug. The 7 old Sanity ids → **308** to the new slug (`next.config.ts` redirects, generated map in `legacy-sanity-ids.ts`); unknown slug → 404 |
| `/blogs` | Redesign (design read: editorial blog for engineers/recruiters, preserve the dark zinc + emerald brand; dials 6/4/3). Latest post as a split feature, the rest as editorial rows (date column, title, excerpt, reading time/views/reactions/comments, tags, thumbnail), tag filter pills (scroll-snap on mobile), totals line, empty/filtered-empty/error states, matching skeleton `loading.tsx`. Static + ISR 10 min. The first diagram stands in as a thumbnail; there are no cover images |
| Post page | Stats header (date, reading time, views, reactions, comments), tracing-beam reader kept, auto-excerpt description hidden, `generateMetadata` (canonical, OG article tags); comments section rendered server-side, sanitised again with DOMPurify, threads to depth 3, single "Discuss on DEV" CTA |
| API | `/api/posts` now returns DEV summaries; `/api/revalidate` also invalidates the `devto` tag |
| Removed | Sanity `BlogList` (infinite scroll), `blog-card`, `PostType` |
| Deps | `isomorphic-dompurify@2.25.0` (already installed via `sanity`, now direct), `server-only`. Image hosts added for DEV uploads, `media2.dev.to` and the S3 diagram bucket |

## Verified
- `tsc --noEmit` clean; ESLint clean on changed files (one pre-existing `<img>` warning in `MarkdownComp`); `next build` passes
  (`/blogs` and `/api/posts` prerendered with 10-minute revalidation, `/posts/[slug]` dynamic).
- `bun dev` on :3000: `/blogs` 200, both post types 200, unknown slug 404, `/posts/fef96ac5-…` → 308 `/posts/debezium-cdc-in-practice-1h1e`.
- Screenshots (headless Chrome): desktop 1440 list and post; mobile 390 list and post (via 390px iframes, because CLI Chrome's minimum window is wider).
  These caught and fixed `&amp;` in descriptions, the duplicated excerpt above the body, and the H1/pills being server-rendered at
  `opacity:0` (an LCP/no-JS risk: entrance fades were removed above the fold).
- Comment sanitiser against an XSS payload: scripts, handlers, `javascript:` URLs, iframes and styles removed; links get `rel="noopener noreferrer nofollow ugc"`.

## Not verified / follow-ups
- No post has comments yet, so a real thread hasn't rendered live (the empty state has).
- **Vercel needs `DEV_TO_API_KEY`** in its environment for page views; without it the site falls back to the public API and hides views.
- Pre-existing, unchanged: Prism hydration mismatch warning on posts with code blocks (`MarkdownComp` highlights after render); nav doesn't mark "Blogs" active on `/posts/*`.
- `next dev` generated `profile-ui/AGENTS.md` (Next.js agent rules). It isn't part of this epic and was left uncommitted.
