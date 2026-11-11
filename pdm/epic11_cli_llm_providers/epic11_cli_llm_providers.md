# Epic 11 — Local Agent CLIs as LLM Providers (agy / Claude Code)

| | |
|---|---|
| **Milestone** | M3.2 |
| **Depends on** | Epic 1 (model factory), Epic 9 (token accounting) |
| **Status** | Implemented 2026-11-11: awaiting owner review |

## Goal

Let the owner run the agent on the AI subscriptions they already pay for, without a provider API key:
any model role (`planner`, `writer`, `fast`, `judge`, `vision`) can be served by the **Antigravity CLI (`agy`)**
or the **Claude Code CLI (`claude`)** already logged in on the machine.

```bash
LLM_DEFAULT_MODEL=agy:gemini-3.8-flash-medium
LLM_FAST_MODEL=claude_code:haiku
```

## Findings that shaped the design (verified 2026-11-11, agy 1.5.3, Claude Code 2.1.220)

| Question | agy | claude |
|---|---|---|
| Headless mode | `-p` print mode, `--output-format json/stream-json` | `-p`, `--output-format json/stream-json` |
| Structured output | `--json-schema <string or file>` → `result.structured_output` | `--json-schema <string>` → `structured_output` |
| Prompt on stdin (prompts can exceed the 128 KB argv limit) | `--input-format stream-json`, line `{"event":"user","message":{"role":"user","content":"…"}}`; `-p=` must be the **last** flag or it swallows the next one | `--input-format stream-json`, line `{"type":"user","message":{…}}` |
| Images (vision role) | stdin accepts **text blocks only**; images are written into the temp workspace and opened with its `read_file` tool | base64 `image` content blocks inline |
| Tools | No flag to disable; the prompt tells it not to use tools. Commands needing permission are auto-denied in headless mode | `--tools ""` disables all tools |
| Usage | `usage.{input,output,thinking,cache_read}_tokens` | `usage.{input,cache_creation_input,cache_read_input,output}_tokens`, `total_cost_usd` |
| Pydantic schemas with `$defs`/`$ref` | OK (`DiagramSpec` round-trips) | OK |

## Stories

| # | Story | Pts |
|---|---|---|
| S1 | `CliChatModel(BaseChatModel)` with agy and claude backends: stdin prompt, JSON parsing, usage metadata, timeout + kill, retries, per-CLI concurrency limit | 5 |
| S2 | `with_structured_output` mapped to `--json-schema`, with a JSON-in-text fallback; output still validated by `invoke_structured` | 2 |
| S3 | Vision: LangChain `image_url` data-URL / `image` blocks → inline (claude) or workspace file (agy) | 2 |
| S4 | Model factory routes `agy:` / `claude_code:` to the CLI model; config (`AGY_BIN`, `CLAUDE_CODE_BIN`, `*_EXTRA_ARGS`, `CLI_LLM_TIMEOUT_SECONDS`, `CLI_LLM_MAX_CONCURRENCY`) | 2 |
| S5 | Budget: CLI calls record tokens but cost 0 USD (`compute_token_cost`) | 1 |
| S6 | Docker: `docker-compose.cli.yml` + `make up CLI=1` mounts host binaries and logins into the api container | 2 |

### Acceptance criteria
- A task runs end to end with every role on `agy:` or `claude_code:` and no provider API key set (except `GOOGLE_API_KEY` for embeddings/thumbnails).
- Provider API keys and app secrets in `.env` never reach the CLI process (env allowlist), so `ANTHROPIC_API_KEY` can't switch Claude Code to API billing.
- A missing binary, non-zero exit, error result or timeout raises `CliModelError` with a readable message; the existing node error handling applies.
- Existing `<provider>:<model>` strings keep working unchanged.

### Out of scope
- Embeddings and image generation through the CLIs (they don't expose them).
- Streaming tokens to the dashboard (the graph doesn't stream model tokens today).

## Implementation notes (2026-11-11)

- **Code:** `api/src/modules/agent/infrastructure/adapters/cli_chat_model.py` (new), `langchain_model_factory.py` (`_cli_model`),
  `configs/config.py` (CLI settings; `LLM_VISION_MODEL` now validated like the other roles), `agent/utils.py` (0 USD for CLI models).
- **Multi-turn history** (repair turns in `invoke_structured`, diagram feedback) is flattened into one `<user>/<assistant>` transcript, because print mode runs a single turn. System messages go to `--system-prompt-file` (claude) or an `<instructions>` block (agy).
- **Timeout:** `max(LLM_TIMEOUT_SECONDS, CLI_LLM_TIMEOUT_SECONDS=600)`; agent CLIs carry start-up time and ~8–17k tokens of their own system prompt per call (agy).
- **Ignored for CLIs:** per-role temperature and max-tokens (no CLI flag). Use the model id (e.g. `-low`/`-high` agy variants) or `*_EXTRA_ARGS=--effort low`.
- **Docker:** verified that both host binaries and logins work inside `python:3.12-slim` as uid 1000 with the mounts in `docker-compose.cli.yml`. The api image is not rebuilt by this epic; `make up CLI=1` is all that's needed.

### Verified
- `tests/unit/test_cli_chat_model.py`: 14 tests with fake CLIs (argv/stdin shape, `-p=` last, schema file, images, env allowlist, usage mapping, retries, timeout kill, missing binary, factory wiring, 0 USD).
- Full unit suite: 415 passed (419 after the agy schema fix below).
- Live, through the real factory: `DiagramSpec` structured output and an image question on `agy:gemini-3.8-flash-low` (8.6 s / 9.0 s) and `claude_code:haiku` (9.9 s / 4.3 s).
- Both CLIs answered from inside a `python:3.12-slim` container with the overlay's mounts.
- Integration suite: `make test-integration` → 451 passed (unit + integration, against the compose Postgres).

- **End to end in the running stack (`make up CLI=1`)**, a research-only task submitted through the dashboard's *New task* form
  (headless Chromium in the renderer container), topic "What is PostgreSQL MVCC and how does VACUUM relate to it?":

  | Engine | Result | Calls | Tokens | Wall time | Budget cost |
  |---|---|---|---|---|---|
  | `claude_code:sonnet` | completed: 14 sources assessed, 91 claims, 9 key findings | 16 | 215k | ~6.5 min | $0 |
  | `agy:gemini-3.8-flash-medium` | completed: 13 sources assessed, 88 claims, 6 key findings | 15 | 194k | ~4.5 min | $0 |

### Fix found by the end-to-end run: agy and nested schemas
The first agy run failed in `plan_research` (`StructuredOutputError: ResearchPlanOut`). agy exposes `--json-schema` to the model as
the parameters of its `finish` tool, and the model didn't see Pydantic's `$defs`: it sent strings for `questions[]`/`queries[]`,
the tool rejected them, and the model gave up and answered in prose (it also tried a `grep` in `/tmp`, which headless mode denied).
Fix: `inline_refs()` makes every schema self-contained before it reaches either CLI, and the agy prompt now says to answer via
`finish` and retry it on invalid arguments. Reproduced with the real planner prompt: 0/2 before, 2/2 after. Regression tests:
`test_inline_refs_*`, `test_agy_gets_inlined_schema_and_finish_tool_instruction`, `test_every_app_schema_inlines`.
Unit suite after the fix: 419 passed.

### Not verified
- An **article** task (outline → draft → diagram with the vision review) on CLI models; only research-only tasks were run.
- Node timeouts are unchanged (e.g. `plan_research` 300 s) and are shorter than `CLI_LLM_TIMEOUT_SECONDS`; observed CLI calls took 20–110 s.
