import pytest
from pydantic import ValidationError

from src.configs.config import Config


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """Config must only see what each test passes. `make test-integration` exports the real .env into the
    environment, which pydantic-settings reads even with _env_file=None (real secrets leaked into assertions)."""
    for name in Config.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def make(**overrides) -> Config:
    return Config(_env_file=None, db_url="postgresql://u:p@localhost/db", **overrides)


def test_model_string_requires_provider_prefix():
    with pytest.raises(ValidationError, match="provider"):
        make(llm_default_model="claude-sonnet")


def test_model_string_accepts_provider_and_blank():
    config = make(llm_default_model="anthropic:claude-sonnet-5-5", llm_writer_model="")
    assert config.llm_default_model == "anthropic:claude-sonnet-5-5"
    assert config.llm_writer_model is None


def test_cors_origins_accepts_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert make().cors_origins == ["http://a.test", "http://b.test"]


def test_empty_secret_becomes_none_and_secret_values_lists_real_ones():
    config = make(agent_api_key="", openai_api_key="sk-openai-123456", langsmith_api_key="ls-key-123456")
    assert config.agent_api_key is None
    assert set(config.secret_values()) == {"sk-openai-123456", "ls-key-123456"}


def test_tracing_needs_flag_and_key():
    assert make(langsmith_tracing=True).tracing_enabled is False
    assert make(langsmith_tracing=True, langsmith_api_key="ls-key-123456").tracing_enabled is True
