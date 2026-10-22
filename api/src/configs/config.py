import os
import sys
from typing import Annotated

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# Provider SDKs read their keys from os.environ, so keys declared here are exported at startup.
PROVIDER_ENV_KEYS = ("anthropic_api_key", "openai_api_key", "google_api_key")


class Config(BaseSettings):
    app_name: str = "blog-agent-api"
    env: str = "local"
    port: int = 8000
    debug: bool = False

    # Plain libpq URL: postgresql://user:password@host:port/dbname
    db_url: str
    checkpoint_schema: str = "langgraph"
    checkpoint_pool_size: int = 5

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://127.0.0.1:3100",
        "http://localhost:3100",
    ]
    agent_api_key: SecretStr | None = None
    rate_limit_default: str = "120/minute"
    rate_limit_strict: str = "10/minute"

    log_level: str = "INFO"
    log_json: bool = True
    data_dir: str = "./data"

    # LLM roles: "<provider>:<model>" strings passed to init_chat_model
    llm_default_model: str | None = None
    llm_planner_model: str | None = None
    llm_writer_model: str | None = None
    llm_fast_model: str | None = None
    llm_judge_model: str | None = None
    llm_planner_temperature: float = 0.2
    llm_writer_temperature: float = 0.7
    llm_fast_temperature: float = 0.0
    llm_judge_temperature: float = 0.0
    llm_planner_max_tokens: int = 4096
    llm_writer_max_tokens: int = 8192
    llm_fast_max_tokens: int = 2048
    llm_judge_max_tokens: int = 4096
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "blog-agent-local"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_hide_inputs: bool = False
    langsmith_hide_outputs: bool = False

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "agent_api_key",
        "anthropic_api_key",
        "openai_api_key",
        "google_api_key",
        "langsmith_api_key",
        mode="before",
    )
    @classmethod
    def empty_secret_is_none(cls, value):
        return None if value in (None, "") else value

    @field_validator(
        "llm_default_model",
        "llm_planner_model",
        "llm_writer_model",
        "llm_fast_model",
        "llm_judge_model",
        mode="before",
    )
    @classmethod
    def validate_model_string(cls, value):
        if value in (None, ""):
            return None
        provider, sep, model = str(value).partition(":")
        if not sep or not provider or not model:
            raise ValueError("must look like '<provider>:<model>', e.g. 'anthropic:claude-sonnet-5-5'")
        return value

    @property
    def tracing_enabled(self) -> bool:
        return self.langsmith_tracing and self.langsmith_api_key is not None

    def secret_values(self) -> list[str]:
        values = []
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, SecretStr) and len(value.get_secret_value()) >= 6:
                values.append(value.get_secret_value())
        return values

    def export_provider_env(self) -> None:
        for name in PROVIDER_ENV_KEYS:
            value = getattr(self, name)
            if value is not None:
                os.environ.setdefault(name.upper(), value.get_secret_value())


def load_config() -> Config:
    try:
        return Config()
    except ValidationError as exc:
        problems = "\n".join(
            f"  - {'.'.join(str(p) for p in err['loc']).upper()}: {err['msg']}" for err in exc.errors()
        )
        sys.exit(f"Invalid blog-agent configuration (check blog-agent/.env):\n{problems}")


config = load_config()
