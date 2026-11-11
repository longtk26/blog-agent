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
    llm_vision_model: str | None = None       # must accept images; diagram visual review (E10-S7)
    llm_planner_temperature: float = 0.2
    llm_writer_temperature: float = 0.7
    llm_fast_temperature: float = 0.0
    llm_judge_temperature: float = 0.0
    llm_vision_temperature: float = 0.0
    llm_planner_max_tokens: int = 4096
    llm_writer_max_tokens: int = 8192
    llm_fast_max_tokens: int = 2048
    llm_judge_max_tokens: int = 4096
    llm_vision_max_tokens: int = 2048
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2

    # Local agent CLIs as LLM providers (Epic 11): LLM_*_MODEL=agy:<model> or claude_code:<model>.
    # They use the owner's CLI login, not an API key. Embeddings and thumbnails still need GOOGLE_API_KEY.
    agy_bin: str = "agy"
    claude_code_bin: str = "claude"
    agy_extra_args: Annotated[list[str], NoDecode] = []
    claude_code_extra_args: Annotated[list[str], NoDecode] = []
    cli_llm_timeout_seconds: float = 600.0
    cli_llm_max_concurrency: int = 2

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # Research (Epic 2). search_provider "auto" = tavily when TAVILY_API_KEY is set, else duckduckgo.
    search_provider: str = "auto"
    tavily_api_key: SecretStr | None = None
    research_max_queries: int = 20
    research_max_sources: int = 40
    research_max_rounds: int = 4
    research_quality_threshold: float = 0.5
    research_domain_denylist: Annotated[list[str], NoDecode] = []
    research_source_chars_for_llm: int = 20000
    fetch_timeout_seconds: float = 15.0
    fetch_max_bytes: int = 2_000_000
    fetch_allow_private_hosts: bool = False
    extract_concurrency: int = 4
    assess_concurrency: int = 3
    workflow_max_concurrency: int = 2
    node_timeout_seconds: float = 900.0

    # Drafting (Epic 3)
    draft_max_sections: int = 9
    draft_max_self_revisions: int = 2
    draft_min_judge_score: int = 3
    draft_evidence_claims: int = 80

    # Review (Epic 4)
    max_review_rounds: int = 10              # safety net on AI revision requests per task
    review_research_max_queries: int = 4     # budget for follow-up research asked for in review
    review_research_max_sources: int = 6
    revision_max_chars: int = 200_000

    # Publishing (Epic 5)
    sanity_project_id: str = "sanity_project_id"
    sanity_dataset: str = "blogs"
    sanity_api_version: str = "2025-01-20"
    sanity_api_write_token: SecretStr | None = None
    sanity_site_base_url: str = "https://leon-pham.vercel.app"
    sanity_studio_base_url: str = "https://sanity_studio_base_url.sanity.studio"
    sanity_test_dataset: str | None = None
    sanity_generate_thumbnail: bool = True
    thumbnail_model: str = "gemini-3.1-flash-image"
    blogs_export_enabled: bool = False
    blogs_dir: str = "../blogs"

    # DEV Community Publishing (Epic 8)
    dev_to_api_key: SecretStr | None = None
    dev_to_base_url: str = "https://dev.to/api"

    # Image hosting for published articles (Epic 12). "auto" = s3 when S3_BUCKET and AWS keys are set, else sanity.
    # Dev.to bodies use this host for diagrams/images; Sanity documents always keep their own Sanity assets.
    image_host: str = "auto"
    aws_access_key: SecretStr | None = None      # .env names: AWS_ACCESS_KEY / AWS_SECRET_KEY
    aws_secret_key: SecretStr | None = None
    s3_bucket: str | None = None
    s3_region: str = "ap-southeast-1"
    s3_prefix: str = "diagrams/"                 # the only publicly readable folder of the bucket
    s3_public_base_url: str | None = None        # e.g. a CloudFront domain; default is the bucket's S3 URL

    # Style & Knowledge (Epic 6)
    embedding_model: str = "google_genai:gemini-embedding-001"
    embedding_dim: int = 768
    style_sample_max_tokens: int = 1500
    copy_detection_ngram: int = 8
    copy_detection_warn_threshold: float = 0.15
    copy_detection_block_threshold: float = 0.30
    copy_detection_run_words: int = 40

    # Observability & Evaluation (Epic 9)
    prompt_source: str = "files"
    trace_max_doc_chars: int = 5000
    task_default_max_cost_usd: float = 2.0

    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    # Editable Diagrams (Epic 7)
    diagram_renderer_url: str = "http://renderer:8080"
    diagram_render_timeout: float = 45.0       # client side; the renderer caps each render at 30 s itself
    diagram_max_concurrent_renders: int = 2
    # Diagram quality (Epic 10)
    diagram_visual_review: bool = True         # vision-model review of the rendered PNG + bounded repair
    diagram_review_max_rounds: int = 2         # extra generations driven by review feedback

    langsmith_project: str = "blog-agent-local"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_hide_inputs: bool = False
    langsmith_hide_outputs: bool = False
    langsmith_agent_id: str | None = None
    langsmith_agent_environment: str | None = None

    model_pricing: dict[str, dict[str, float]] = {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0, "cached": 0.30},
        "claude-3-7-sonnet": {"input": 3.0, "output": 15.0, "cached": 0.30},
        "claude-sonnet": {"input": 3.0, "output": 15.0, "cached": 0.30},
        "claude-3-5-haiku": {"input": 0.80, "output": 4.0, "cached": 0.08},
        "claude-haiku": {"input": 0.80, "output": 4.0, "cached": 0.08},
        "gpt-4o": {"input": 2.50, "output": 10.0, "cached": 1.25},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached": 0.075},
        "gemini-3.8-flash-lite": {"input": 0.50, "output": 2.50, "cached": 0.05},
        "gemini-3.8-flash": {"input": 0.75, "output": 3.75, "cached": 0.075},
        "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50, "cached": 0.025},
        "gemini-3.1-flash": {"input": 0.50, "output": 2.50, "cached": 0.05},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cached": 0.025},
        "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15, "cached": 0.01},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "cached": 0.01875},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.0, "cached": 0.3125},
        "default": {"input": 2.0, "output": 10.0, "cached": 0.50},
    }

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    @field_validator("agy_extra_args", "claude_code_extra_args", mode="before")
    @classmethod
    def split_args(cls, value):
        if isinstance(value, str):
            return value.split()
        return value

    @field_validator("cors_origins", "research_domain_denylist", mode="before")
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
        "tavily_api_key",
        "langsmith_api_key",
        "sanity_api_write_token",
        "dev_to_api_key",
        "aws_access_key",
        "aws_secret_key",
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
        "llm_vision_model",
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

    @field_validator("image_host")
    @classmethod
    def validate_image_host(cls, value: str) -> str:
        if value not in ("auto", "s3", "sanity"):
            raise ValueError("must be one of: auto, s3, sanity")
        return value

    @field_validator("s3_bucket", "s3_public_base_url", mode="before")
    @classmethod
    def empty_str_is_none(cls, value):
        return None if value in (None, "") else value

    @field_validator("search_provider")
    @classmethod
    def validate_search_provider(cls, value: str) -> str:
        if value not in ("auto", "tavily", "duckduckgo"):
            raise ValueError("must be one of: auto, tavily, duckduckgo")
        return value

    @field_validator("embedding_model")
    @classmethod
    def validate_embedding_model(cls, value: str) -> str:
        provider, sep, model = str(value).partition(":")
        if not sep or not provider or not model:
            raise ValueError("must look like '<provider>:<model>', e.g. 'google_genai:gemini-embedding-001'")
        return value

    @field_validator("embedding_dim")
    @classmethod
    def validate_embedding_dim(cls, value: int) -> int:
        if value <= 0 or value > 2000:
            raise ValueError("embedding_dim must be between 1 and 2000 (HNSW pgvector index limit)")
        return value

    @property
    def resolved_search_provider(self) -> str:
        if self.search_provider == "auto":
            return "tavily" if self.tavily_api_key else "duckduckgo"
        return self.search_provider

    @property
    def resolved_image_host(self) -> str:
        if self.image_host == "auto":
            s3_ready = bool(self.s3_bucket and self.aws_access_key and self.aws_secret_key)
            return "s3" if s3_ready else "sanity"
        return self.image_host

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
