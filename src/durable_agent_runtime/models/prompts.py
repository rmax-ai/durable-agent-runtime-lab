"""Model prompt templates and structured output schemas.

Converts GoalSpecification → model prompts for action proposal generation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Structured output model ──────────────────────────────────────────────


class ProposedAction(BaseModel):
    """LLM-generated action proposal.

    The model fills in this structure via ``response_format.json_schema``.
    After validation, it is converted to a proper ``ActionProposal`` domain object.
    """

    tool_name: str = Field(
        default="run_command",
        description=("Tool to invoke: run_command, read_file, write_file"),
    )
    command: str = Field(
        default="",
        description=("Shell command (for run_command) or file path (for read_file/write_file)"),
    )
    file_content: str = Field(
        default="",
        description="Content to write (for write_file tool)",
    )
    intention: str = Field(
        default="",
        description="Human-readable description of what this action intends to accomplish",
    )
    risk_level: str = Field(
        default="low",
        description="Estimated risk: low, medium, high, critical",
    )
    expected_effects: list[str] = Field(
        default_factory=list,
        description="Expected effects of this action",
    )
    is_terminal: bool = Field(
        default=False,
        description="True if this is the final action (goal achieved, no more steps needed)",
    )


# ── Prompt templates ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a deterministic agent runtime that proposes shell commands to accomplish \
software engineering goals.

## Your Role
You receive a goal specification and propose one action at a time. Each action is \
a shell command that moves the work forward.

## Available Tools
- **run_command**: Execute a shell command in the workspace repository
- **read_file**: Read a file's contents
- **write_file**: Write content to a file (NOT available in some configurations)

## Guidelines
1. Propose exactly ONE action per response
2. Every action must be an idempotent shell command (safe to re-run)
3. Use `run_command` for: editing files (sed, patch), running tests, git ops, ls
4. If goal already complete, set `is_terminal: true` with command: echo done
5. Estimate risk level honestly:
   - low: read-only (ls, cat, grep, git status, pytest --collect-only)
   - medium: file modifications (sed, cp, mv, git add), running tests
   - high: destructive operations (rm, git reset --hard)
6. Always prefer safe, small steps over ambitious multi-step commands
7. Repository is already cloned at the workspace path — operate on it directly"""


def build_action_prompt(
    goal_text: str,
    repository_path: str = ".",
    tools: list[str] | None = None,
    conversation_history: list[str] | None = None,
    step_number: int = 1,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) pair for action proposal.

    Args:
        goal_text: The normalized goal description
        repository_path: Path to the target repository
        tools: List of available tool names
        conversation_history: Previous steps and their outputs (for baseline loop)
        step_number: Current step number (1-indexed)
    """
    parts: list[str] = []

    parts.append("## Goal")
    parts.append(goal_text)
    parts.append("")
    parts.append("## Workspace")
    parts.append(f"Repository: {repository_path}")
    parts.append(f"Step: {step_number}")

    if tools:
        parts.append("")
        parts.append("## Available Tools")
        parts.append(", ".join(tools))

    if conversation_history:
        parts.append("")
        parts.append("## Previous Steps")
        for entry in conversation_history:
            parts.append(f"- {entry}")

    parts.append("")
    parts.append("## Instructions")
    parts.append(
        "Propose the next action. If all steps are complete, "
        "set `is_terminal: true` with a summary command."
    )

    user_prompt = "\n".join(parts)
    return SYSTEM_PROMPT, user_prompt
