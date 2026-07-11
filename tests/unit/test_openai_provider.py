"""Tests for OpenAIProvider using mock HTTP transport (no real API calls)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from durable_agent_runtime.models.base import ModelRequest
from durable_agent_runtime.models.openai_provider import OpenAIProvider

# --- Pydantic models used as response_model fixtures ---


class SimpleResponse(BaseModel):
    result: str


class ComplexResponse(BaseModel):
    name: str
    count: int
    tags: list[str]


# --- Helpers ---


def _make_mock_client(
    body: dict[str, Any] | None = None, status_code: int = 200
) -> httpx.AsyncClient:
    """Create an AsyncClient with a mock transport that returns a fixed response."""

    async def handler(request: httpx.Request) -> httpx.Response:
        # Verify request shape
        req_body = json.loads(request.content)
        assert "model" in req_body, "Request must include model"
        assert "messages" in req_body, "Request must include messages"
        assert "response_format" in req_body, "Request must include response_format"
        assert req_body["response_format"]["type"] == "json_schema"
        assert "json_schema" in req_body["response_format"]

        # Verify auth header
        assert request.headers.get("Authorization") == "Bearer test-key-123"

        resp_body = body or {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1720000000,
            "model": "gpt-4o-2024-08-06",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {"result": "success", "name": "test", "count": 42, "tags": ["a", "b"]}
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 10,
                "total_tokens": 35,
            },
        }
        return httpx.Response(status_code=status_code, json=resp_body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _make_inspecting_client(
    inspector=None,
    body: dict[str, Any] | None = None,
) -> httpx.AsyncClient:
    """Create a mock client that calls *inspector* with the request before returning."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if inspector:
            inspector(request)
        resp_body = body or {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1720000001,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": json.dumps({"result": "ok"})},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        return httpx.Response(status_code=200, json=resp_body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- Fixtures ---


@pytest.fixture
def provider():
    """OpenAIProvider with a test API key and mock client (no env var needed)."""
    return OpenAIProvider(api_key="test-key-123", model="gpt-4o", client=_make_mock_client())


@pytest.fixture
def request_simple():
    return ModelRequest(user_prompt="Return a result string", response_model_name="SimpleResponse")


@pytest.fixture
def request_with_system():
    return ModelRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="Return a complex object.",
        response_model_name="ComplexResponse",
        max_tokens=2000,
        temperature=0.3,
    )


# --- Tests ---


@pytest.mark.asyncio
async def test_request_shape(provider: OpenAIProvider, request_simple: ModelRequest):
    """Verify the HTTP request sent to OpenAI has the correct shape."""
    response = await provider.generate_structured(request_simple, SimpleResponse)
    assert response.model == "gpt-4o-2024-08-06"
    assert response.provider == "openai"
    assert response.finish_reason == "stop"
    assert response.input_tokens == 25
    assert response.output_tokens == 10
    assert response.content["result"] == "success"


@pytest.mark.asyncio
async def test_structured_validation(provider: OpenAIProvider, request_with_system: ModelRequest):
    """Verify the response is validated against the Pydantic response_model."""
    response = await provider.generate_structured(request_with_system, ComplexResponse)
    assert response.content["name"] == "test"
    assert response.content["count"] == 42
    assert response.content["tags"] == ["a", "b"]


@pytest.mark.asyncio
async def test_system_prompt_included():
    """Verify system prompt is included in the messages array."""
    captured_requests: list[httpx.Request] = []

    def inspector(request: httpx.Request) -> None:
        captured_requests.append(request)

    client = _make_inspecting_client(inspector=inspector)
    p = OpenAIProvider(api_key="test-key-123", model="gpt-4o", client=client)

    request = ModelRequest(
        system_prompt="You are an AI.",
        user_prompt="Do something.",
    )
    await p.generate_structured(request, SimpleResponse)

    assert len(captured_requests) == 1
    req_body = json.loads(captured_requests[0].content)
    messages = req_body["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are an AI."
    assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_no_system_prompt():
    """Verify only user message when no system prompt."""
    captured_requests: list[httpx.Request] = []

    def inspector(request: httpx.Request) -> None:
        captured_requests.append(request)

    client = _make_inspecting_client(inspector=inspector)
    p = OpenAIProvider(api_key="test-key-123", model="gpt-4o", client=client)

    request = ModelRequest(user_prompt="Just do it.")
    await p.generate_structured(request, SimpleResponse)

    req_body = json.loads(captured_requests[0].content)
    messages = req_body["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


@pytest.mark.asyncio
async def test_api_error_propagated():
    """Verify HTTP errors are propagated."""
    client = _make_mock_client(status_code=401)
    p = OpenAIProvider(api_key="test-key-123", client=client)

    with pytest.raises(httpx.HTTPStatusError):
        await p.generate_structured(ModelRequest(user_prompt="test"), SimpleResponse)


def test_api_key_from_env(monkeypatch: pytest.MonkeyPatch):
    """Verify API key is loaded from environ when not passed."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-key-456")
    p = OpenAIProvider()
    assert p.api_key == "env-key-456"
    assert p.model == "gpt-4o"


def test_api_key_explicit_preferred():
    """Verify explicit API key takes precedence over env var."""
    p = OpenAIProvider(api_key="explicit-key")
    assert p.api_key == "explicit-key"


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch):
    """Verify missing API key raises ValueError."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider()


def test_custom_base_url():
    """Verify custom base_url is used."""
    p = OpenAIProvider(api_key="key", base_url="https://custom.example.com/v1")
    assert p.base_url == "https://custom.example.com/v1"


def test_custom_model():
    """Verify custom model is used."""
    p = OpenAIProvider(api_key="key", model="gpt-4o-mini")
    assert p.model == "gpt-4o-mini"
