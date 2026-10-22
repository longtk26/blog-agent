import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from src.configs.config import Config


request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
task_id_ctx: ContextVar[str | None] = ContextVar("task_id", default=None)

HEADER_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|api-key|x-api-key|x-agent-key)(['\"]?\s*[:=]\s*['\"]?)(bearer\s+)?[^\s'\",}]+"
)
REDACTED = "[REDACTED]"


class Redactor:
    def __init__(self, secrets: list[str] | None = None):
        self.secrets = sorted(set(secrets or []), key=len, reverse=True)

    def __call__(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, REDACTED)
        return HEADER_SECRET_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        record.task_id = task_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def __init__(self, redactor: Redactor):
        super().__init__()
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "task_id"):
            if getattr(record, key, None):
                payload[key] = getattr(record, key)
        if isinstance(getattr(record, "context", None), dict):
            payload["context"] = record.context
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return self.redactor(json.dumps(payload, default=str))


class TextFormatter(logging.Formatter):
    def __init__(self, redactor: Redactor):
        super().__init__("%(asctime)s %(levelname)-5s [%(name)s] %(message)s")
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        ids = " ".join(
            f"{key}={getattr(record, key)}" for key in ("request_id", "task_id") if getattr(record, key, None)
        )
        if isinstance(getattr(record, "context", None), dict):
            ids = f"{ids} {json.dumps(record.context, default=str)}".strip()
        return self.redactor(f"{line} {ids}".rstrip())


def setup_logging(config: Config) -> None:
    redactor = Redactor(config.secret_values())
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter(redactor) if config.log_json else TextFormatter(redactor))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(config.log_level.upper())
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    for name in ("uvicorn", "uvicorn.error", "fastapi"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
