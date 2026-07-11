"""OpenAI-compatible model provider using httpx (no openai SDK dependency)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import BaseModel

from durable_agent_runtime.models.base import ModelRequest, ModelResponse


class OpenAIProvider:
    """OpenAI-compatible model provider.

    Uses httpx directly instead of the openai Python SDK.
    Supports structured output via response_format with json_schema.

    Pass a custom ``client`` with ``httpx.MockTransport`` for testing
    without real API calls.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be provided or set in the environment")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = client or httpx.AsyncClient(timeout=120.0)

    async def generate_structured(
        self,
        request: ModelRequest,
        response_model: type[BaseModel],
    ) -> ModelResponse:
        """Send a chat completion request with structured output."""
        schema_json = response_model.model_json_schema()
        json_schema = {
            "name": response_model.__name__,
            "schema": schema_json,
            "strict": True,
        }

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": json_schema,
            },
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        content_raw = message.get("content", "{}")
        content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw

        usage = data.get("usage", {})
        finish_reason = choice.get("finish_reason", "stop")

        # Validate against response_model
        validated = response_model.model_validate(content)

        # Extract cached tokens if available
        cached_tokens = 0
        prompt_tokens_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_tokens_details, dict):
            cached_tokens = prompt_tokens_details.get("cached_tokens", 0)

        return ModelResponse(
            content=validated.model_dump(),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cached_tokens=cached_tokens,
            model=data.get("model", self.model),
            provider="openai",
            finish_reason=finish_reason,
        )
