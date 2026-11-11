"""Chat model backed by a local coding-agent CLI instead of a provider API key (Epic 11).

Two CLIs are supported, chosen by the provider part of the model string:

- ``agy:<model>``          Google Antigravity CLI (``agy models`` lists ids, e.g. ``gemini-3.8-flash-medium``)
- ``claude_code:<model>``  Claude Code CLI (``sonnet``, ``opus``, ``haiku`` or a full model id)

``<model>`` may be ``default`` to use the CLI's own default model.

Each call runs the CLI once in print mode inside a fresh temporary directory, with the prompt on stdin
(prompts can exceed Linux's 128 KB argv limit) and JSON output. Structured output maps to the CLI's
``--json-schema`` flag; the result is still validated against the Pydantic schema by the caller.

The CLIs authenticate with the owner's own login (subscription), so calls are recorded with their token
counts but cost 0 USD in the task budget. They are agents, not plain completion endpoints: tools are
disabled where the CLI allows it (Claude Code) and the prompt tells the model not to use them (agy).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.language_models.base import LangSmithParams
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, PrivateAttr

from src.configs.logger import get_logger

logger = get_logger(__name__)

CliProvider = Literal["agy", "claude_code"]
CLI_PROVIDERS: tuple[str, ...] = ("agy", "claude_code")

# Only these variables reach the CLI. Provider API keys and the app's own secrets are left out, so the CLI
# uses the owner's login and an ANTHROPIC_API_KEY in .env can't silently switch Claude Code to API billing.
_ENV_ALLOWLIST = (
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TZ", "TMPDIR", "TERM",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS",
    "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR",
)

_PLAIN_LLM_RULES = (
    "You are being called as a plain language-model endpoint by another program, not as a coding agent. "
    "Answer only from the content of this message. Do not use tools, do not run commands, do not search "
    "the web and do not read or write files"
)

_DATA_URL = re.compile(r"^data:(?P<mime>image/[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$", re.S)
_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.S)
_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp", "image/gif": "gif"}

_semaphores: dict[tuple[str, int], asyncio.Semaphore] = {}


class CliModelError(RuntimeError):
    """The CLI failed, timed out or answered with an error result."""


@dataclass
class _Image:
    mime: str
    data: bytes


@dataclass
class _Prompt:
    system: str
    text: str
    images: list[_Image] = field(default_factory=list)


@dataclass
class _CliResult:
    text: str
    structured: Any | None
    usage: UsageMetadata
    metadata: dict[str, Any]


def _semaphore(provider: str, limit: int) -> asyncio.Semaphore:
    key = (provider, max(1, limit))
    sem = _semaphores.get(key)
    if sem is None:
        sem = _semaphores[key] = asyncio.Semaphore(key[1])
    return sem


def _block_image(block: dict) -> _Image | None:
    btype = block.get("type")
    if btype == "image_url":
        url = block.get("image_url")
        url = url.get("url") if isinstance(url, dict) else url
        match = _DATA_URL.match(url or "")
        if match:
            return _Image(match["mime"], base64.b64decode(match["data"]))
    elif btype == "image":
        # LangChain standard block ({"source_type": "base64", "data", "mime_type"}) or Anthropic-style.
        source = block.get("source") if isinstance(block.get("source"), dict) else block
        data = source.get("data") or source.get("base64")
        mime = source.get("mime_type") or source.get("media_type") or "image/png"
        if data and (source.get("source_type", "base64") == "base64" or source.get("type") == "base64"):
            return _Image(mime, base64.b64decode(data))
    return None


def _content_parts(content: Any) -> tuple[str, list[_Image]]:
    if isinstance(content, str):
        return content, []
    texts: list[str] = []
    images: list[_Image] = []
    for block in content or []:
        if isinstance(block, str):
            texts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "text":
                texts.append(str(block.get("text", "")))
            elif (image := _block_image(block)) is not None:
                images.append(image)
            elif block.get("type") == "image_url":
                url = block.get("image_url")
                texts.append(f"[image: {url.get('url') if isinstance(url, dict) else url}]")
    return "\n".join(t for t in texts if t), images


def build_prompt(messages: list[BaseMessage]) -> _Prompt:
    """Flatten a chat history into one system prompt + one user turn (print mode runs a single turn)."""
    system_parts: list[str] = []
    turns: list[tuple[str, str]] = []
    images: list[_Image] = []
    for message in messages:
        text, found = _content_parts(message.content)
        images.extend(found)
        if isinstance(message, SystemMessage):
            if text:
                system_parts.append(text)
        else:
            turns.append(("assistant" if isinstance(message, AIMessage) else "user", text))

    if len(turns) == 1 and turns[0][0] == "user":
        body = turns[0][1]
    else:
        body = "\n\n".join(f"<{role}>\n{text}\n</{role}>" for role, text in turns)
        body = (
            "Below is a conversation so far. Write the assistant's next reply to the last user turn.\n\n" + body
        )
    return _Prompt(system="\n\n".join(system_parts), text=body, images=images)


def parse_json_answer(text: str) -> Any | None:
    """Best-effort JSON from a free-text answer (fallback when the CLI returned no structured_output)."""
    text = (text or "").strip()
    if not text:
        return None
    candidates = [text, *(m.group(1) for m in _FENCED_JSON.finditer(text))]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def inline_refs(schema: dict) -> dict:
    """Return a copy of a JSON Schema with every local ``#/$defs/...`` reference replaced by its definition.

    Pydantic puts nested models in ``$defs``. agy turns the schema into the parameters of its ``finish`` tool,
    and the model doesn't see referenced definitions there: it answered with strings where objects were
    required, the tool rejected them and the run ended with no structured output (seen 2026-11-11 with
    ResearchPlanOut). A self-contained schema avoids that. Recursive models keep their ``$ref`` (none today)."""
    defs = {**schema.get("definitions", {}), **schema.get("$defs", {})}

    def resolve(node: Any, stack: tuple[str, ...]) -> Any:
        if isinstance(node, list):
            return [resolve(item, stack) for item in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(("#/$defs/", "#/definitions/")):
            name = ref.rsplit("/", 1)[1]
            if name in defs and name not in stack:
                siblings = {k: v for k, v in node.items() if k != "$ref"}
                return resolve({**defs[name], **siblings}, (*stack, name))
        return {k: resolve(v, stack) for k, v in node.items() if k not in ("$defs", "definitions")}

    resolved = resolve(schema, ())
    if '"$ref"' in json.dumps(resolved) and defs:
        resolved["$defs"] = defs  # recursive model: keep the definitions it still points at
    return resolved


def _usage(input_tokens: int, output_tokens: int, cache_read: int = 0, reasoning: int = 0) -> UsageMetadata:
    usage: UsageMetadata = {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(input_tokens) + int(output_tokens),
    }
    if cache_read:
        usage["input_token_details"] = {"cache_read": int(cache_read)}
    if reasoning:
        usage["output_token_details"] = {"reasoning": int(reasoning)}
    return usage


class CliChatModel(BaseChatModel):
    """LangChain chat model that shells out to ``agy`` or ``claude`` in print mode."""

    provider: CliProvider
    model: str = "default"
    binary: str
    timeout_seconds: float = 120.0
    max_retries: int = 2
    max_concurrency: int = 2
    extra_args: list[str] = []

    _last_metadata: dict[str, Any] = PrivateAttr(default_factory=dict)

    @property
    def _llm_type(self) -> str:
        return f"cli-{self.provider}"

    @property
    def model_name(self) -> str:
        return f"{self.provider}:{self.model}"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"provider": self.provider, "model_name": self.model_name}

    def _get_ls_params(self, stop: list[str] | None = None, **kwargs: Any) -> LangSmithParams:
        params = super()._get_ls_params(stop=stop, **kwargs)
        params["ls_provider"] = self.provider
        params["ls_model_name"] = self.model_name
        return params

    # ---- structured output ----------------------------------------------------------------------------
    def with_structured_output(
        self, schema: dict | type, *, include_raw: bool = False, **kwargs: Any
    ) -> Runnable[LanguageModelInput, Any]:
        if include_raw:
            raise NotImplementedError("CliChatModel.with_structured_output does not support include_raw")
        is_model = isinstance(schema, type) and issubclass(schema, BaseModel)
        json_schema = inline_refs(schema.model_json_schema() if is_model else schema)

        def parse(message: AIMessage) -> Any:
            data = message.additional_kwargs.get("structured_output")
            if data is None:
                data = parse_json_answer(message.text if hasattr(message, "text") else str(message.content))
            if data is None:
                raise ValueError("CLI returned no JSON matching the schema")
            return schema.model_validate(data) if is_model else data

        return self.bind(json_schema=json_schema) | RunnableLambda(parse, name="CliStructuredOutputParser")

    # ---- generation -------------------------------------------------------------------------------------
    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return asyncio.run(self._agenerate(messages, stop=stop, **kwargs))

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = build_prompt(messages)
        json_schema = kwargs.get("json_schema")
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with _semaphore(self.provider, self.max_concurrency):
                    result = await self._run(prompt, json_schema)
                break
            except CliModelError as exc:
                last_error = exc
                logger.warning(f"{self.model_name} call failed (attempt {attempt + 1}): {exc}")
        else:
            raise CliModelError(f"{self.model_name}: {last_error}") from last_error

        additional: dict[str, Any] = {}
        if result.structured is not None:
            additional["structured_output"] = result.structured
        content = result.text
        if not content and result.structured is not None:
            content = json.dumps(result.structured, ensure_ascii=False)
        message = AIMessage(
            content=content,
            additional_kwargs=additional,
            usage_metadata=result.usage,
            response_metadata={"model_name": self.model_name, "model_provider": self.provider, **result.metadata},
        )
        return ChatResult(generations=[ChatGeneration(message=message)], llm_output={"model_name": self.model_name})

    async def _run(self, prompt: _Prompt, json_schema: dict | None) -> _CliResult:
        with tempfile.TemporaryDirectory(prefix=f"blog-agent-{self.provider}-") as workdir:
            if self.provider == "agy":
                argv, stdin = self._agy_command(prompt, json_schema, Path(workdir))
            else:
                argv, stdin = self._claude_command(prompt, json_schema, Path(workdir))
            stdout = await self._exec(argv, stdin, workdir)
        return self._parse_agy(stdout) if self.provider == "agy" else self._parse_claude(stdout)

    def _model_args(self) -> list[str]:
        return [] if self.model in ("", "default") else ["--model", self.model]

    def _agy_command(self, prompt: _Prompt, json_schema: dict | None, workdir: Path) -> tuple[list[str], bytes]:
        # agy's stream-json input accepts text blocks only, so images are written into the (empty, temporary)
        # workspace and the model is told to open them with its read_file tool.
        rules = _PLAIN_LLM_RULES
        if json_schema is not None:
            rules += (
                ". Give your final answer by calling your finish tool with arguments that match its schema exactly "
                "(nested objects as objects, not strings); if it reports invalid arguments, fix them and call it "
                "again. That tool is allowed"
            )
        attachments = ""
        if prompt.images:
            names = []
            for i, image in enumerate(prompt.images):
                name = f"image_{i + 1}.{_EXT.get(image.mime, 'png')}"
                (workdir / name).write_bytes(image.data)
                names.append(str(workdir / name))
            rules += ", except: open the attached image file(s) listed below with your read_file tool"
            attachments = "\n\nAttached image file(s), open each one before answering:\n" + "\n".join(
                f"- {n}" for n in names
            )
        text = f"<instructions>\n{rules}.\n"
        if prompt.system:
            text += f"\n{prompt.system}\n"
        text += f"</instructions>\n\n{prompt.text}{attachments}"

        argv = [self.binary, "--input-format", "stream-json", "--output-format", "stream-json",
                "--disable-slash-commands", *self._model_args(), *self.extra_args]
        if json_schema is not None:
            schema_path = workdir / "schema.json"
            schema_path.write_text(json.dumps(json_schema))
            argv += ["--json-schema", str(schema_path)]
        argv.append("-p=")  # agy reads the turn from stdin; -p must come last or it swallows the next flag
        line = json.dumps({"event": "user", "message": {"role": "user", "content": text}})
        return argv, (line + "\n").encode()

    def _claude_command(self, prompt: _Prompt, json_schema: dict | None, workdir: Path) -> tuple[list[str], bytes]:
        system = _PLAIN_LLM_RULES + "."
        if prompt.system:
            system += "\n\n" + prompt.system
        system_path = workdir / "system.md"
        system_path.write_text(system)
        argv = [self.binary, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--tools", "", "--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config",
                "--system-prompt-file", str(system_path), *self._model_args(), *self.extra_args]
        if json_schema is not None:
            argv += ["--json-schema", json.dumps(json_schema)]
        content: list[dict] = [
            {"type": "image", "source": {"type": "base64", "media_type": img.mime,
                                         "data": base64.b64encode(img.data).decode("ascii")}}
            for img in prompt.images
        ]
        content.append({"type": "text", "text": prompt.text})
        line = json.dumps({"type": "user", "message": {"role": "user", "content": content}})
        return argv, (line + "\n").encode()

    async def _exec(self, argv: list[str], stdin: bytes, cwd: str) -> str:
        env = {k: v for k, v in os.environ.items() if k in _ENV_ALLOWLIST}
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv, cwd=cwd, env=env,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise CliModelError(
                f"'{self.binary}' not found. Install it, or set {self.provider.upper()}_BIN to its path "
                "(inside Docker, start with `make up CLI=1`)."
            ) from exc
        try:
            out, err = await asyncio.wait_for(proc.communicate(stdin), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise CliModelError(f"timed out after {self.timeout_seconds:.0f}s") from exc
        stdout = out.decode("utf-8", "replace")
        if proc.returncode != 0 and '"result"' not in stdout:
            detail = (err.decode("utf-8", "replace") or stdout).strip()[-800:]
            raise CliModelError(f"exit code {proc.returncode}: {detail}")
        return stdout

    @staticmethod
    def _events(stdout: str) -> list[dict]:
        events = []
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def _parse_agy(self, stdout: str) -> _CliResult:
        result = next((e.get("result") for e in reversed(self._events(stdout)) if e.get("event") == "result"), None)
        if not isinstance(result, dict):
            raise CliModelError(f"no result event in agy output: {stdout.strip()[-500:]}")
        if result.get("status") != "SUCCESS":
            raise CliModelError(f"agy status {result.get('status')}: {result.get('error') or 'no detail'}")
        u = result.get("usage") or {}
        thinking = int(u.get("thinking_tokens") or 0)
        return _CliResult(
            text=str(result.get("response") or "").strip(),
            structured=result.get("structured_output"),
            usage=_usage(u.get("input_tokens") or 0, int(u.get("output_tokens") or 0), u.get("cache_read_tokens") or 0,
                         thinking),
            metadata={"conversation_id": result.get("conversation_id"), "num_turns": result.get("num_turns")},
        )

    def _parse_claude(self, stdout: str) -> _CliResult:
        result = next((e for e in reversed(self._events(stdout)) if e.get("type") == "result"), None)
        if result is None:
            raise CliModelError(f"no result event in claude output: {stdout.strip()[-500:]}")
        if result.get("is_error") or result.get("subtype") not in (None, "success"):
            raise CliModelError(f"claude {result.get('subtype')}: {str(result.get('result') or '')[:500]}")
        u = result.get("usage") or {}
        cache_read = int(u.get("cache_read_input_tokens") or 0)
        input_tokens = int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0) + cache_read
        return _CliResult(
            text=str(result.get("result") or "").strip(),
            structured=result.get("structured_output"),
            usage=_usage(input_tokens, u.get("output_tokens") or 0, cache_read),
            metadata={
                "session_id": result.get("session_id"),
                "num_turns": result.get("num_turns"),
                # What the same tokens would cost on the API; not charged to the task budget.
                "notional_cost_usd": result.get("total_cost_usd"),
            },
        )
