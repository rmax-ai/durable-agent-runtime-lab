# ADR-004: Provider-neutral model interface

**Status:** Accepted

**Date:** 2026-07-11

**Context:**

The runtime must support at least two model providers: a mock/deterministic provider for testing and an OpenAI-compatible provider for real execution. The spec requires a common interface (Section 26). Options:

- **Use each provider's native SDK directly:** Fast to implement, but couples every call site to a specific provider. Switching providers means rewriting all model interaction code.
- **LangChain / LiteLLM:** Provides abstraction but introduces heavy dependency chains. Overkill for a research project that needs exactly one interface method (`generate_structured`).
- **Custom Protocol class:** A single `ModelProvider` Protocol with one method. Implementations are thin adapters. Zero framework overhead.

**Decision:**

Use a **custom `ModelProvider` Protocol** with a single `generate_structured` method.

```python
class ModelProvider(Protocol):
    async def generate_structured(
        self,
        request: ModelRequest,
        response_model: type[BaseModel],
    ) -> ModelResponse:
        ...
```

Required implementations:
1. `MockProvider` — deterministic fixtures, fault injection (timeout, malformed output, repeated responses), token/cost simulation
2. `OpenAIProvider` — wraps the OpenAI-compatible API, returns `ModelResponse` with typed output

The Protocol is not imported at runtime — it's a structural type. Any object with a `generate_structured` method matching the signature satisfies the interface.

**Consequences:**

- **Easier:** All tests run without external model access via `MockProvider`.
- **Easier:** Adding a new provider (Anthropic, Google, local) requires ~50 lines of adapter code.
- **Easier:** Model router can swap providers per role (advisor/planner/worker) at call time.
- **Harder:** No built-in streaming, token counting, or retry logic in the interface. These are implemented in the orchestrator layer, not the provider.
- **Harder:** Provider-specific features (cached tokens, prompt caching) require the `ModelResponse` to carry optional metadata — providers report what they support.
