from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from src.configs import config as app_config
from src.configs.config import Config
from src.libs.exceptions import BadRequestException, ErrorCode
from src.modules.agent.infrastructure.adapters.cli_chat_model import CLI_PROVIDERS, CliChatModel
from src.modules.agent.ports.output.model_factory import IModelFactory, ModelRole, ModelSpec


class LangChainModelFactory(IModelFactory):
    def __init__(self, config: Config):
        self.config = config
        self._cache: dict[ModelRole, BaseChatModel] = {}

    def spec(self, role: ModelRole) -> ModelSpec:
        role = ModelRole(role)
        return ModelSpec(
            role=role,
            model=getattr(self.config, f"llm_{role.value}_model") or self.config.llm_default_model,
            temperature=getattr(self.config, f"llm_{role.value}_temperature"),
            max_tokens=getattr(self.config, f"llm_{role.value}_max_tokens"),
            timeout_seconds=self.config.llm_timeout_seconds,
            max_retries=self.config.llm_max_retries,
        )

    def get(self, role: ModelRole) -> BaseChatModel:
        role = ModelRole(role)
        if role in self._cache:
            return self._cache[role]

        spec = self.spec(role)
        if spec.model is None:
            raise BadRequestException(
                f"No model configured for role '{role.value}'. Set LLM_{role.value.upper()}_MODEL or LLM_DEFAULT_MODEL.",
                code=ErrorCode.LLM_NOT_CONFIGURED,
            )
        if spec.provider in CLI_PROVIDERS:
            model = self._cli_model(spec)
        else:
            model = init_chat_model(
                spec.model,
                temperature=spec.temperature,
                max_tokens=spec.max_tokens,
                timeout=spec.timeout_seconds,
                max_retries=spec.max_retries,
            )
        self._cache[role] = model
        return model

    def _cli_model(self, spec: ModelSpec) -> BaseChatModel:
        """agy / claude_code: a local CLI logged in with the owner's account (Epic 11).
        Temperature and max_tokens can't be passed to the CLIs; the CLI timeout is the larger of the
        role timeout and CLI_LLM_TIMEOUT_SECONDS because agent CLIs add start-up and tool overhead."""
        provider = spec.provider
        return CliChatModel(
            provider=provider,
            model=spec.model.split(":", 1)[1],
            binary=self.config.agy_bin if provider == "agy" else self.config.claude_code_bin,
            timeout_seconds=max(spec.timeout_seconds, self.config.cli_llm_timeout_seconds),
            max_retries=spec.max_retries,
            max_concurrency=self.config.cli_llm_max_concurrency,
            extra_args=self.config.agy_extra_args if provider == "agy" else self.config.claude_code_extra_args,
        )


@lru_cache
def get_model_factory() -> IModelFactory:
    return LangChainModelFactory(app_config)


IModelFactoryDep = Annotated[IModelFactory, Depends(get_model_factory)]
