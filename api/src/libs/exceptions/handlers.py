from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.configs.logger import get_logger, request_id_ctx
from .base_exception import BaseException
from .error_codes import ErrorCode

logger = get_logger(__name__)


def error_body(code: str, message: str, details: Any = None) -> dict:
    body = {"code": code, "message": message, "request_id": request_id_ctx.get()}
    if details is not None:
        body["details"] = details
    return body


def _split_detail(detail: Any) -> tuple[str, Any]:
    if isinstance(detail, str):
        return detail, None
    return "Request failed", detail


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BaseException)
    async def handle_base_exception(_: Request, exc: BaseException):
        message, details = _split_detail(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, message, details))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException):
        message, details = _split_detail(exc.detail)
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.HTTP_ERROR
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message, details))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content=error_body(ErrorCode.VALIDATION_ERROR, "Invalid request", details)
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(_: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429, content=error_body(ErrorCode.RATE_LIMITED, f"Rate limit exceeded: {exc.detail}")
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500, content=error_body(ErrorCode.INTERNAL_ERROR, "Internal server error")
        )
