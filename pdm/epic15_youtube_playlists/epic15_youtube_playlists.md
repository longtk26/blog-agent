# Epic 15 — YouTube Playlists on the Website (profile-ui)

| | |
|---|---|
| **Milestone** | M3.2 |
| **Depends on** | Epic 13 (blog page patterns, format helpers) |
| **Code** | `profile-ui/` (separate repo) |
| **Status** | Implemented 2026-11-11: awaiting owner review |

## Goal
Show the "Useful for dev" channel (`UCl4IoMkBqSjd5CecCMaAmvQ`, @usefulfordev) on the website, **organised by playlist**.

## Research (YouTube Data API v3 with `YOUTUBE_API_KEY`, 2026-11-11)
- `channels` → title, handle, stats (3 videos, 37 views, 1 subscriber), uploads playlist.
- `playlists?channelId=` → `totalResults: 3`, but only **2 public** playlists are returned to an API key
  ("Leetcode - Data structure & Algorithm" (1), "System design" (2)); the third is presumably private.
- `playlistItems` (per playlist + uploads) and `videos` (duration ISO 8601, views, thumbnails up to `maxres`).
- Quota: one refresh ≈ 2 + (playlists + 1) + 1 units; cached for an hour, so a few hundred units a day at most (limit 10,000).

## What changed (profile-ui)
| Area | Change |
|---|---|
| Data | `external/youtube/index.ts` (`server-only`): `getVideoLibrary()` returns the channel, public playlists in their own order (sorted by newest video), and public uploads in no playlist ("More uploads"). Fetch cache 1 h, tag `youtube` |
| Page | `/videos`: header with channel totals and one "Subscribe on YouTube" CTA; playlist jump links (scroll-snap on mobile); a section per playlist (title, count, total duration linking to the playlist); 2-column video cards. Empty and error states. Static + ISR 1 h |
| Player | Click-to-load: a thumbnail (`next/image`, `i.ytimg.com`) plus a play button; pressing it mounts the `youtube-nocookie.com` embed with autoplay. No iframes load on page view |
| Nav / profile | "Videos" added to the navbar. The profile page's YouTube card CTA now goes to `/videos` ("Browse videos") instead of leaving the site |
| Revalidate | `/api/revalidate` also clears the `youtube` tag and `/videos` |
| Shared | `formatDuration` added to `app/blogs/_components/format.ts` (server and client safe) |

## Verified
- `tsc` and ESLint clean; `next build` passes with `/videos` prerendered (`initialRevalidateSeconds: 3600`).
- `bun dev` on :3000: `/videos`, `/blogs` and `/profile` return 200. Screenshots at desktop 1440 and mobile 390 show both playlists, all 3 videos with correct durations and views, and the nav highlighting "Videos".
- The no-cookie embed URL responds 200. A server/client boundary error (`formatDuration` imported into the server page from a client file) was caught on the first request and fixed.

## Needs the owner
- **Vercel env:** add `YOUTUBE_API_KEY` (and `DEV_TO_API_KEY` from Epic 13). Locally the key was copied into `profile-ui/.env.local` (gitignored).
- Consider restricting the API key in Google Cloud to the YouTube Data API (it is used server-side only, so an HTTP-referrer restriction would break it).
- Clicking play hasn't been exercised in a real browser session (headless screenshots only).
