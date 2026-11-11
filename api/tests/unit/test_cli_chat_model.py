"""Epic 11: agy / claude_code CLIs as LLM providers. Fake CLIs record their argv/stdin and print canned JSON."""

import base64
import json
import stat
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from src.configs.config import Config
from src.modules.agent.infrastructure.adapters.cli_chat_model import (
    CliChatModel,
    CliModelError,
    build_prompt,
    inline_refs,
    parse_json_answer,
)
from src.modules.agent.infrastructure.adapters.langchain_model_factory import LangChainModelFactory
from src.modules.agent.nodes.llm import invoke_structured
from src.modules.agent.ports.output import ModelRole
from src.modules.agent.utils import compute_token_cost

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


class Answer(BaseModel):
    title: str
    tags: list[str]


FAKE = r'''#!{python}
import json, os, sys
log = os.environ.get("HOME") + "/calls.jsonl"
stdin = sys.stdin.read()
files = {{n: open(n, "rb").read().hex() for n in os.listdir(".")}}
with open(log, "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "stdin": stdin, "cwd_files": files,
                        "env": sorted(os.environ)}}) + "\n")
mode = open(os.environ["HOME"] + "/mode").read().strip()
if mode == "crash":
    sys.stderr.write("boom"); sys.exit(3)
if mode == "hang":
    import time; time.sleep(30)
structured = {{"title": "T", "tags": ["a"]}} if "--json-schema" in sys.argv else None
if "{kind}" == "agy":
    status = "ERROR" if mode == "error" else "SUCCESS"
    print(json.dumps({{"event": "init"}}))
    print(json.dumps({{"event": "result", "result": {{"status": status, "error": "quota",
        "response": "pong" if mode != "textjson" else 'Sure: ```json\n{{"title": "T2", "tags": []}}\n```',
        "structured_output": None if mode == "textjson" else structured, "conversation_id": "c1", "num_turns": 1,
        "usage": {{"input_tokens": 100, "output_tokens": 20, "thinking_tokens": 5, "cache_read_tokens": 7}}}}}}))
else:
    print(json.dumps({{"type": "system"}}))
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": mode == "error", "result": "pong",
        "structured_output": structured, "session_id": "s1", "num_turns": 1, "total_cost_usd": 0.01,
        "usage": {{"input_tokens": 10, "cache_creation_input_tokens": 50, "cache_read_input_tokens": 40,
                   "output_tokens": 9}}}}))
'''


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "mode").write_text("ok")
    bins = {}
    for kind in ("agy", "claude"):
        path = tmp_path / kind
        path.write_text(FAKE.format(python=sys.executable, kind="agy" if kind == "agy" else "claude"))
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        bins[kind] = str(path)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("GOOGLE_API_KEY", "should-not-leak")
    return home, bins


def calls(home: Path) -> list[dict]:
    return [json.loads(line) for line in (home / "calls.jsonl").read_text().splitlines()]


def model(bins, provider="agy", **kw) -> CliChatModel:
    binary = bins["agy"] if provider == "agy" else bins["claude"]
    return CliChatModel(provider=provider, model=kw.pop("model", "gemini-3.8-flash-low"), binary=binary,
                        timeout_seconds=kw.pop("timeout_seconds", 20), max_retries=kw.pop("max_retries", 0), **kw)


async def test_agy_text_call_sends_prompt_on_stdin_and_reports_usage(fake_home):
    home, bins = fake_home
    msg = await model(bins).ainvoke([SystemMessage("Be terse."), HumanMessage("Say pong")])
    assert msg.content == "pong"
    assert msg.usage_metadata["input_tokens"] == 100
    assert msg.usage_metadata["output_tokens"] == 20
    assert msg.usage_metadata["input_token_details"] == {"cache_read": 7}
    assert msg.response_metadata["model_name"] == "agy:gemini-3.8-flash-low"
    call = calls(home)[0]
    assert call["argv"][-1] == "-p="  # must be last, or agy treats the next flag as the prompt
    assert ["--model", "gemini-3.8-flash-low"] == call["argv"][call["argv"].index("--model"):][:2]
    event = json.loads(call["stdin"])
    assert event["event"] == "user"
    assert "Be terse." in event["message"]["content"] and "Say pong" in event["message"]["content"]
    # API keys never reach the CLI
    assert "ANTHROPIC_API_KEY" not in call["env"] and "GOOGLE_API_KEY" not in call["env"]


async def test_agy_structured_output_and_schema_file(fake_home):
    home, bins = fake_home
    result = await invoke_structured(model(bins), Answer, [HumanMessage("Title please")])
    assert result == Answer(title="T", tags=["a"])
    argv = calls(home)[0]["argv"]
    schema_path = argv[argv.index("--json-schema") + 1]
    assert schema_path.endswith("schema.json")
    assert json.loads(bytes.fromhex(calls(home)[0]["cwd_files"]["schema.json"]))["title"] == "Answer"


async def test_agy_structured_falls_back_to_json_in_text(fake_home):
    home, bins = fake_home
    (home / "mode").write_text("textjson")
    result = await model(bins).with_structured_output(Answer).ainvoke([HumanMessage("x")])
    assert result == Answer(title="T2", tags=[])


async def test_agy_images_are_written_to_the_workspace(fake_home):
    home, bins = fake_home
    msg = HumanMessage(content=[{"type": "text", "text": "Review"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG}"}}])
    await model(bins).ainvoke([msg])
    call = calls(home)[0]
    assert bytes.fromhex(call["cwd_files"]["image_1.png"]) == base64.b64decode(PNG)
    assert "image_1.png" in json.loads(call["stdin"])["message"]["content"]


async def test_claude_code_disables_tools_and_sends_images_inline(fake_home):
    home, bins = fake_home
    msg = HumanMessage(content=[{"type": "text", "text": "Review"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG}"}}])
    out = await model(bins, provider="claude_code", model="sonnet").with_structured_output(Answer).ainvoke(
        [SystemMessage("sys rules"), msg]
    )
    assert out == Answer(title="T", tags=["a"])
    call = calls(home)[0]
    argv = call["argv"]
    assert argv[argv.index("--tools") + 1] == ""
    assert "--no-session-persistence" in argv and "--strict-mcp-config" in argv
    assert "sys rules" in bytes.fromhex(call["cwd_files"]["system.md"]).decode()
    content = json.loads(call["stdin"])["message"]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["data"] == PNG
    assert content[-1] == {"type": "text", "text": "Review"}


async def test_claude_code_usage_counts_cache_tokens_as_input(fake_home):
    _, bins = fake_home
    msg = await model(bins, provider="claude_code", model="default").ainvoke("hi")
    assert msg.usage_metadata["input_tokens"] == 100
    assert msg.usage_metadata["input_token_details"] == {"cache_read": 40}
    assert msg.response_metadata["notional_cost_usd"] == 0.01


@pytest.mark.parametrize("mode", ["crash", "error"])
async def test_failures_raise_after_retries(fake_home, mode):
    home, bins = fake_home
    (home / "mode").write_text(mode)
    with pytest.raises(CliModelError):
        await model(bins, max_retries=1).ainvoke("hi")
    assert len(calls(home)) == 2


async def test_timeout_kills_the_process(fake_home):
    home, bins = fake_home
    (home / "mode").write_text("hang")
    with pytest.raises(CliModelError, match="timed out"):
        await model(bins, timeout_seconds=0.5).ainvoke("hi")


async def test_missing_binary_is_a_clear_error():
    m = CliChatModel(provider="agy", binary="/nonexistent/agy", timeout_seconds=5, max_retries=0)
    with pytest.raises(CliModelError, match="not found"):
        await m.ainvoke("hi")


def test_build_prompt_flattens_multi_turn_history():
    prompt = build_prompt([SystemMessage("S"), HumanMessage("Q1"), AIMessage("A1"), HumanMessage("fix it")])
    assert prompt.system == "S"
    assert "<user>\nQ1\n</user>" in prompt.text and "<assistant>\nA1\n</assistant>" in prompt.text
    assert prompt.text.rstrip().endswith("</user>")


def test_parse_json_answer():
    assert parse_json_answer('{"a": 1}') == {"a": 1}
    assert parse_json_answer('Here:\n```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json_answer("no json here") is None


def test_factory_builds_cli_models_from_config():
    config = Config(_env_file=None, db_url="postgresql://u:p@localhost/db",
                    llm_default_model="agy:gemini-3.8-flash-medium", llm_fast_model="claude_code:haiku",
                    agy_bin="/opt/agy", claude_code_extra_args="--effort low", llm_timeout_seconds=30)
    factory = LangChainModelFactory(config)
    writer = factory.get(ModelRole.WRITER)
    fast = factory.get(ModelRole.FAST)
    assert isinstance(writer, CliChatModel) and writer.binary == "/opt/agy"
    assert writer.model == "gemini-3.8-flash-medium" and writer.timeout_seconds == 600
    assert isinstance(fast, CliChatModel) and fast.binary == "claude" and fast.extra_args == ["--effort", "low"]
    assert factory.spec(ModelRole.WRITER).provider == "agy"


def test_cli_calls_cost_nothing_in_the_budget():
    assert compute_token_cost("agy:claude-sonnet-5-5-high", 1_000_000, 1_000_000) == 0.0
    assert compute_token_cost("claude_code:sonnet", 1_000_000, 1_000_000) == 0.0
    assert compute_token_cost("anthropic:claude-sonnet-5-5", 1_000_000, 0) > 0


class Inner(BaseModel):
    query: str


class Outer(BaseModel):
    queries: list[Inner]
    first: Inner | None = None


def test_inline_refs_makes_nested_models_self_contained():
    schema = inline_refs(Outer.model_json_schema())
    assert "$defs" not in schema and '"$ref"' not in json.dumps(schema)
    assert schema["properties"]["queries"]["items"]["properties"]["query"]["type"] == "string"


class Node(BaseModel):
    children: list["Node"] = []


def test_inline_refs_keeps_recursive_definitions():
    schema = inline_refs(Node.model_json_schema())
    assert "Node" in schema.get("$defs", {}) or '"$ref"' not in json.dumps(schema)


async def test_agy_gets_inlined_schema_and_finish_tool_instruction(fake_home):
    home, bins = fake_home
    with pytest.raises(ValidationError):  # the fake's canned answer doesn't fit Outer; only the request matters
        await model(bins).with_structured_output(Outer).ainvoke([HumanMessage("x")])
    call = calls(home)[0]
    sent = json.loads(bytes.fromhex(call["cwd_files"]["schema.json"]))
    assert "$defs" not in sent and sent["properties"]["queries"]["items"]["type"] == "object"
    assert "finish tool" in json.loads(call["stdin"])["message"]["content"]


def test_every_app_schema_inlines():
    import importlib, inspect, pkgutil
    import src.modules as root

    seen = 0
    for info in pkgutil.walk_packages(root.__path__, "src.modules."):
        if ".schemas" not in info.name and not info.name.endswith("diagram_spec"):
            continue
        module = importlib.import_module(info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseModel) and cls.__module__ == module.__name__:
                inline_refs(cls.model_json_schema())
                seen += 1
    assert seen > 5
