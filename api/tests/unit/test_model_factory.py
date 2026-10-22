from unittest.mock import patch

import pytest

from src.configs.config import Config
from src.libs.exceptions import BadRequestException
from src.modules.agent.infrastructure.adapters.langchain_model_factory import LangChainModelFactory
from src.modules.agent.ports.output import ModelRole


def make_config(**overrides) -> Config:
    return Config(_env_file=None, db_url="postgresql://u:p@localhost/db", **overrides)


def test_roles_fall_back_to_default_model():
    factory = LangChainModelFactory(
        make_config(llm_default_model="anthropic:claude-sonnet-5-5", llm_fast_model="anthropic:claude-haiku-5-5")
    )
    assert factory.describe() == {
        "planner": "anthropic:claude-sonnet-5-5",
        "writer": "anthropic:claude-sonnet-5-5",
        "fast": "anthropic:claude-haiku-5-5",
        "judge": "anthropic:claude-sonnet-5-5",
    }
    assert factory.spec(ModelRole.FAST).provider == "anthropic"


def test_unconfigured_role_raises_llm_not_configured():
    factory = LangChainModelFactory(make_config())
    assert factory.is_configured(ModelRole.WRITER) is False
    with pytest.raises(BadRequestException) as exc:
        factory.get(ModelRole.WRITER)
    assert exc.value.code == "LLM_NOT_CONFIGURED"


def test_get_passes_role_settings_and_caches():
    factory = LangChainModelFactory(
        make_config(llm_default_model="openai:some-model", llm_writer_temperature=0.9, llm_writer_max_tokens=1234)
    )
    path = "src.modules.agent.infrastructure.adapters.langchain_model_factory.init_chat_model"
    with patch(path) as init_chat_model:
        first = factory.get(ModelRole.WRITER)
        second = factory.get(ModelRole.WRITER)
    assert first is second
    init_chat_model.assert_called_once_with(
        "openai:some-model", temperature=0.9, max_tokens=1234, timeout=120.0, max_retries=2
    )
