"""OpenAI-compatible model provider using httpx (no openai SDK dependency)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import BaseModel

from durable_agent_runtime.models.base import (
    ModelAuthenticationError,
    ModelProviderError,
    ModelRateLimitError,
    ModelRequest,
    ModelResponse,
    ModelStructuredOutputError,
    ModelTransientError,
)


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
        model: str = "gpt-5.4-mini",
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.name = "openai"
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be provided or set in the environment")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = client
        self._transport = transport
        self._timeout = timeout

    async def generate_structured(
        self,
        request: ModelRequest,
        response_model: type[BaseModel],
    ) -> ModelResponse:
        """Send a chat completion request with structured output."""
        schema_json = self._normalize_json_schema(response_model.model_json_schema())
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
            "max_completion_tokens": request.max_tokens,
            # Structured responses are more reliable when decoding is deterministic.
            "temperature": 0.0,
        }

        resp = await self._send_request(body)

        try:
            data = resp.json()
        except ValueError as exc:
            raise ModelProviderError("OpenAI response was not valid JSON") from exc

        choice = data["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")
        content = self._parse_message_content(message, finish_reason)

        usage = data.get("usage", {})

        # Validate against response_model
        try:
            validated = response_model.model_validate(content)
        except Exception as exc:
            raise ModelStructuredOutputError(
                f"OpenAI structured response did not match {response_model.__name__}"
            ) from exc

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

    async def aclose(self) -> None:
        """Close a shared injected HTTP client if present."""
        if self._client is not None:
            await self._client.aclose()

    async def _send_request(self, body: dict[str, Any]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        try:
            if self._client is not None:
                resp = await self._client.post(url, headers=headers, json=body)
            else:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    transport=self._transport,
                ) as client:
                    resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.TimeoutException as exc:
            raise ModelTransientError("OpenAI request timed out") from exc
        except httpx.NetworkError as exc:
            raise ModelTransientError("OpenAI network error") from exc

    def _parse_message_content(
        self,
        message: dict[str, Any],
        finish_reason: str,
    ) -> dict[str, Any]:
        refusal = message.get("refusal")
        if refusal:
            raise ModelStructuredOutputError(f"OpenAI refusal: {refusal}")

        if finish_reason == "length":
            raise ModelStructuredOutputError("OpenAI response was truncated before completion")
        if finish_reason == "content_filter":
            raise ModelStructuredOutputError("OpenAI response was blocked by content filtering")

        content_raw = message.get("content")
        if content_raw is None:
            raise ModelStructuredOutputError("OpenAI response did not include message content")

        if isinstance(content_raw, dict):
            return content_raw

        if isinstance(content_raw, list):
            text_parts = []
            for part in content_raw:
                if not isinstance(part, dict):
                    continue
                text_value = part.get("text")
                if isinstance(text_value, str):
                    text_parts.append(text_value)
            content_raw = "".join(text_parts)

        if not isinstance(content_raw, str) or not content_raw.strip():
            raise ModelStructuredOutputError("OpenAI response content was empty")

        try:
            parsed = self._parse_json_like_content(content_raw)
        except json.JSONDecodeError as exc:
            preview = self._preview_content(content_raw)
            raise ModelStructuredOutputError(
                f"OpenAI response content was not valid JSON: {preview}"
            ) from exc

        if not isinstance(parsed, dict):
            raise ModelStructuredOutputError("OpenAI structured response must be a JSON object")
        return parsed

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> ModelProviderError:
        status = exc.response.status_code
        detail = self._extract_error_detail(exc.response)

        if status in {401, 403}:
            return ModelAuthenticationError(
                f"OpenAI authentication failed (HTTP {status}): {detail}"
            )
        if status == 429:
            return ModelRateLimitError(f"OpenAI rate limit exceeded (HTTP 429): {detail}")
        if status in {408, 409} or 500 <= status < 600:
            return ModelTransientError(f"OpenAI transient failure (HTTP {status}): {detail}")
        return ModelProviderError(f"OpenAI request failed (HTTP {status}): {detail}")

    def _extract_error_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                error_type = error.get("type")
                error_code = error.get("code")
                parts = [str(part) for part in (message, error_type, error_code) if part]
                if parts:
                    return " | ".join(parts)[:400]

        text = response.text.strip()
        if text:
            return text[:400]
        return "no response body"

    def _normalize_json_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Normalize Pydantic schema for OpenAI structured-output constraints."""

        def visit(node: Any) -> Any:
            if isinstance(node, dict):
                normalized = {key: visit(value) for key, value in node.items()}
                if normalized.get("type") == "object":
                    if "additionalProperties" not in normalized:
                        normalized["additionalProperties"] = False
                    properties = normalized.get("properties")
                    if isinstance(properties, dict):
                        normalized["required"] = list(properties.keys())
                return normalized
            if isinstance(node, list):
                return [visit(item) for item in node]
            return node

        return visit(schema)

    def _parse_json_like_content(self, content: str) -> Any:
        """Parse JSON content, tolerating code fences and surrounding prose."""
        stripped = content.strip()

        candidates = [stripped]

        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                candidates.append("\n".join(lines[1:-1]).strip())

        first_brace = stripped.find("{")
        last_brace = stripped.rfind("}")
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            candidates.append(stripped[first_brace : last_brace + 1])

        seen: set[str] = set()
        last_error: json.JSONDecodeError | None = None
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc
            try:
                return self._raw_decode_first_json_object(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise json.JSONDecodeError("No JSON candidate found", stripped, 0)

    def _preview_content(self, content: str) -> str:
        """Return a compact preview of non-JSON content for error reporting."""
        compact = " ".join(content.split())
        return compact[:160]

    def _raw_decode_first_json_object(self, content: str) -> Any:
        """Decode the first valid JSON object from a string with trailing prose."""
        decoder = json.JSONDecoder()
        stripped = content.lstrip()

        try:
            parsed, _ = decoder.raw_decode(stripped)
            return parsed
        except json.JSONDecodeError:
            pass

        for idx, char in enumerate(stripped):
            if char != "{":
                continue
            parsed, _ = decoder.raw_decode(stripped[idx:])
            return parsed

        raise json.JSONDecodeError("No JSON object found", stripped, 0)

    def _parse_json_like_content(self, content: str) -> Any:
        """Parse JSON content, tolerating code fences and surrounding prose."""
        stripped = content.strip()

        candidates = [stripped]

        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                candidates.append("\n".join(lines[1:-1]).strip())

        first_brace = stripped.find("{")
        last_brace = stripped.rfind("}")
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            candidates.append(stripped[first_brace : last_brace + 1])

        seen: set[str] = set()
        last_error: json.JSONDecodeError | None = None
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc
            try:
                return self._raw_decode_first_json_object(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise json.JSONDecodeError("No JSON candidate found", stripped, 0)

    def _preview_content(self, content: str) -> str:
        """Return a compact preview of non-JSON content for error reporting."""
        compact = " ".join(content.split())
        return compact[:160]

    def _raw_decode_first_json_object(self, content: str) -> Any:
        """Decode the first valid JSON object from a string with trailing prose."""
        decoder = json.JSONDecoder()
        stripped = content.lstrip()

        try:
            parsed, _ = decoder.raw_decode(stripped)
            return parsed
        except json.JSONDecodeError:
            pass

        for idx, char in enumerate(stripped):
            if char != "{":
                continue
            parsed, _ = decoder.raw_decode(stripped[idx:])
            return parsed

        raise json.JSONDecodeError("No JSON object found", stripped, 0)
