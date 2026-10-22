import hmac
import json
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from src.configs.logger import request_id_ctx
from src.libs.exceptions.error_codes import ErrorCode

# Pure ASGI middlewares (not BaseHTTPMiddleware) so SSE responses stream without buffering.

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def _send_json(send: Send, status: int, code: str, message: str) -> None:
    body = json.dumps({"code": code, "message": message, "request_id": request_id_ctx.get()}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        incoming = _header(scope, b"x-request-id")
        request_id = incoming if incoming and len(incoming) <= 64 else uuid.uuid4().hex
        token = request_id_ctx.set(request_id)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_ctx.reset(token)


class ApiKeyMiddleware:
    """Requires `X-Agent-Key` when AGENT_API_KEY is configured. CORS preflights pass through."""

    def __init__(self, app: ASGIApp, api_key: str | None, exempt_paths: tuple[str, ...] = ("/health",)):
        self.app = app
        self.api_key = api_key
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not self.api_key
            or scope["method"] == "OPTIONS"
            or scope["path"] in self.exempt_paths
        ):
            return await self.app(scope, receive, send)

        provided = _header(scope, b"x-agent-key") or ""
        if not hmac.compare_digest(provided.encode(), self.api_key.encode()):
            return await _send_json(send, 401, ErrorCode.UNAUTHORIZED, "Missing or invalid X-Agent-Key")
        await self.app(scope, receive, send)


class JsonContentTypeMiddleware:
    """Rejects state-changing requests that are not JSON (or multipart on allowed paths).

    Browsers can send cross-site "simple" requests (form posts, no-cors fetch) without a
    preflight; those can never carry `application/json`, so this blocks CSRF-style triggers.
    """

    def __init__(self, app: ASGIApp, multipart_path_prefixes: tuple[str, ...] = ()):
        self.app = app
        self.multipart_path_prefixes = multipart_path_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in STATE_CHANGING_METHODS:
            return await self.app(scope, receive, send)

        content_type = (_header(scope, b"content-type") or "").split(";")[0].strip().lower()
        allowed = content_type == "application/json" or (
            content_type == "multipart/form-data" and scope["path"].startswith(self.multipart_path_prefixes)
        )
        if not allowed:
            return await _send_json(
                send, 415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, "State-changing requests must use application/json"
            )
        await self.app(scope, receive, send)
