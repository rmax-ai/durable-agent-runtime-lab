"""Tool registry and interface definitions (Section 12).

Every tool implements the Tool protocol: validate → execute → compensate.
"""

from typing import Protocol

from pydantic import BaseModel

from durable_agent_runtime.domain.enums import RiskLevel


class ToolContext(BaseModel):
    """Context passed to every tool execution."""

    workspace_root: str
    sandbox_mode: str = "process"
    timeout_seconds: int = 300
    allow_network: bool = False
    max_output_bytes: int = 1_048_576  # 1MB


class ValidationResult(BaseModel):
    """Result of tool argument validation."""

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class ToolResult(BaseModel):
    """Result of tool execution."""

    success: bool
    output: str = ""
    exit_code: int = 0
    artifacts: list[str] = []
    error: str = ""


class CompensationResult(BaseModel):
    """Result of tool compensation (undo)."""

    success: bool
    reverted: list[str] = []
    error: str = ""


class Tool(Protocol):
    """Protocol that all tools must implement (Section 12)."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    risk_level: RiskLevel

    def validate(self, arguments: BaseModel, context: ToolContext) -> ValidationResult: ...

    def execute(self, arguments: BaseModel, context: ToolContext) -> ToolResult: ...

    def compensate(self, result: ToolResult, context: ToolContext) -> CompensationResult: ...


class ToolRegistry:
    """Registry of available tools, keyed by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def list_risky(self, max_risk: RiskLevel = RiskLevel.HIGH) -> list[str]:
        """Return tool names at or below max_risk."""
        return [
            name for name, tool in self._tools.items() if tool.risk_level.value <= max_risk.value
        ]
