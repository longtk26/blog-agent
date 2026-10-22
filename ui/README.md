# Blog Agent — UI

Next.js 16 (App Router, Cache Components) dashboard for the blog agent. Conventions: `blog-agent/.agents/skills/nextjs-skills`.

```bash
pnpm install
AGENT_API_URL=http://127.0.0.1:8100 pnpm dev   # http://127.0.0.1:3100 (or `make dev` from blog-agent/)
pnpm check-types && pnpm lint
```

- The browser only calls `/api/agent/*` (`src/app/api/agent/[...path]/route.ts`). The proxy forwards requests to `AGENT_API_URL`, adds `AGENT_API_KEY` on the server, and streams SSE through.
- Features live in `src/features/<feature>/{api,components,hooks,query-keys.ts,types.ts}`.
- Layout primitives live in `src/components/layout`. shadcn primitives live in `src/components/ui`; don't edit them.
