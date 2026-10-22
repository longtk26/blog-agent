import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from src.libs.exceptions import register_exception_handlers
from src.libs.security import ApiKeyMiddleware, JsonContentTypeMiddleware, RequestContextMiddleware


def build_app(api_key: str | None) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/things")
    async def things():
        return []

    @app.post("/things")
    async def create_thing():
        return {"created": True}

    app.add_middleware(JsonContentTypeMiddleware)
    app.add_middleware(ApiKeyMiddleware, api_key=api_key)
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://127.0.0.1:3100"], allow_methods=["*"], allow_headers=["*"]
    )
    app.add_middleware(RequestContextMiddleware)
    return app


@pytest.fixture
def client():
    return TestClient(build_app("local-key-123"))


def test_api_key_required_when_configured(client):
    response = client.get("/things")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert client.get("/things", headers={"X-Agent-Key": "wrong"}).status_code == 401
    assert client.get("/things", headers={"X-Agent-Key": "local-key-123"}).status_code == 200


def test_health_is_exempt_and_preflight_passes(client):
    assert client.get("/health").status_code == 200
    preflight = client.options(
        "/things",
        headers={"Origin": "http://127.0.0.1:3100", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code == 200


def test_no_api_key_configured_allows_requests():
    assert TestClient(build_app(None)).get("/things").status_code == 200


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": {"a": "1"}},  # HTML form post
        {"content": b"x", "headers": {"Content-Type": "text/plain"}},
        {},  # bodyless no-cors fetch
    ],
)
def test_state_changing_requests_must_be_json(kwargs):
    client = TestClient(build_app(None))
    response = client.post("/things", **kwargs)
    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_json_post_allowed_and_request_id_echoed():
    client = TestClient(build_app(None))
    response = client.post("/things", json={}, headers={"X-Request-ID": "abc123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "abc123"
