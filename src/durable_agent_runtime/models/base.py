"""Model provider interface and mock implementation (Section 26, ADR-004).

Provider-neutral interface: ModelProvider protocol with generate_structured.
Mock provider for deterministic testing with fault injection.
"""

from typing import Any, Protocol

from pydantic import BaseModel


class ModelRequest(BaseModel):
    """Request to a model provider."""

    system_prompt: str = ""
    user_prompt: str
    response_model_name: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    metadata: dict[str, Any] = {}


class ModelResponse(BaseModel):
    """Structured response from a model provider."""

    content: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    model: str = ""
    provider: str = ""
    finish_reason: str = "stop"


class ModelProvider(Protocol):
    """Provider-neutral model interface (Section 26)."""

    async def generate_structured(
        self,
        request: ModelRequest,
        response_model: type[BaseModel],
    ) -> ModelResponse: ...


class MockProvider:
    """Deterministic mock provider for testing.

    Supports:
    - Fixed fixtures (map prompt → response)
    - Fault injection (timeout, malformed output, repeated response)
    - Token and cost simulation
    """

    def __init__(self, name: str = "mock") -> None:
        self.name = name
        self.model = "mock/v1"
        self._fixtures: dict[str, dict[str, Any]] = {}
        self._faults: list[str] = []
        self.call_count = 0

    def set_fixture(self, prompt_hint: str, response: dict[str, Any]) -> None:
        """Register a fixture — when prompt_hint appears in the user_prompt, return response."""
        self._fixtures[prompt_hint] = response

    def inject_fault(self, fault: str) -> None:
        """Inject a fault: 'timeout', 'malformed', 'empty'."""
        self._faults.append(fault)

    async def generate_structured(
        self,
        request: ModelRequest,
        response_model: type[BaseModel],
    ) -> ModelResponse:
        """Return a fixture or default response."""
        self.call_count += 1

        # Check for injected faults
        if "timeout" in self._faults:
            raise TimeoutError("Mock timeout injected")
        if "empty" in self._faults:
            return ModelResponse(
                content={}, input_tokens=10, output_tokens=0, model=self.model, provider=self.name
            )

        # Find matching fixture
        for hint, response in self._fixtures.items():
            if hint in request.user_prompt:
                return ModelResponse(
                    content=response,
                    input_tokens=len(request.user_prompt) // 4,
                    output_tokens=len(str(response)) // 4,
                    model=self.model,
                    provider=self.name,
                )

        # Default: echo back a structured response
        return ModelResponse(
            content={
                "message": f"Mock response to: {request.user_prompt[:50]}...",
                "call_number": self.call_count,
            },
            input_tokens=len(request.user_prompt) // 4,
            output_tokens=50,
            model=self.model,
            provider=self.name,
        )
