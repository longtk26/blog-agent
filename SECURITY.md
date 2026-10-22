# Security notes

## Threat model

- **One user, one machine.** The stack runs through Docker Compose, and every port is bound to `127.0.0.1`. There are no user accounts.
- **Untrusted web content.** Pages retrieved during research may contain prompt-injection text (Epic 2). That content is treated as data, never as instructions. Nodes that read it have no tools that can publish.
- **Untrusted model output.** Every structured output is validated with Pydantic before use. Markdown is sanitised before preview (Epic 4).
- **Other websites in your browser.** A malicious page could try to make your browser call `127.0.0.1`. The defences against that are listed below.

## Secrets

| Secret | Location | Never in |
|---|---|---|
| LLM provider keys, LangSmith key, Sanity/Dev.to tokens | `blog-agent/.env`, which only the `api` service reads | the UI bundle, prompts, graph state, traces, logs |
| `AGENT_API_KEY` | `.env`; the `ui` **server** gets it through Compose env | the browser (it is not `NEXT_PUBLIC_*`) |

`.env` is git-ignored. `.env.example` holds no values.

## Controls (Epic 1)

| Control | Where |
|---|---|
| Ports bound to `127.0.0.1` | `docker-compose.yml` |
| The browser calls the same-origin proxy `/api/agent/*`. The key is added on the server. | `ui/src/lib/server/agent-proxy.ts` |
| The proxy rejects cross-site state-changing requests, using `Sec-Fetch-Site`/`Origin` | `agent-proxy.ts` |
| Optional `X-Agent-Key` check, compared in constant time. Only `/health` is exempt. | `api/src/libs/security/middlewares.py` |
| State-changing requests must be `application/json`. This blocks form posts and `no-cors` fetches, which need no preflight. | `JsonContentTypeMiddleware` |
| CORS allows only the UI origin | `api/src/main.py` |
| Rate limits: a global default, with stricter limits on costly or side-effecting routes | `api/src/libs/security/rate_limit.py` |
| Log redaction: known secret values plus `Authorization`/`api-key`/`x-agent-key` headers | `api/src/configs/logger.py` |
| Trace redaction: our own LangSmith client with an anonymizer that masks configured secrets. Env-based auto-tracing is disabled so nothing is sent unredacted. Inputs and outputs can optionally be hidden. | `langsmith_tracing.py` |
| Errors returned to clients are sanitised (`code`, `message`, `request_id`). Stack traces only go to logs. | `api/src/libs/exceptions/handlers.py` |
| Containers run as non-root users | `api/Dockerfile`, `ui/Dockerfile` |

## Planned (later epics)

- The publishing approval gate is bound to the content hash and destination, and it is enforced server-side (Epics 4–5).
- SSRF guards for web extraction (Epic 2).
- SVG sanitisation (Epics 5 and 7).
