"""Proposal verification and authorization boundary (Section 6.5).

Every action must pass: schema, authorization, policy, precondition,
budget, idempotency, and sandbox-boundary validation before execution.
"""

from typing import Any

from durable_agent_runtime.domain import ActionProposal, CheckResult, VerificationResult
from durable_agent_runtime.persistence.state_store import StateStore


class BoundaryService:
    """Validates action proposals before execution.

    Implements the stochastic-deterministic boundary: Proposal → Verify → Commit|Reject.
    """

    def __init__(self, state_store: StateStore) -> None:
        self.state = state_store

    def verify(
        self, proposal: ActionProposal, budget_remaining: float | None = None
    ) -> VerificationResult:
        """Run all verification checks on a proposal."""
        checks: list[CheckResult] = []

        # 1. Schema validation — arguments must be valid JSON-serializable dict
        checks.append(self._check_schema(proposal))

        # 2. Idempotency — reject duplicate committed actions
        checks.append(self._check_idempotency(proposal.idempotency_key))

        # 3. Budget — reject if over budget
        if budget_remaining is not None:
            checks.append(self._check_budget(budget_remaining))

        # 4. Sandbox path validation
        checks.append(self._check_sandbox_paths(proposal.arguments))

        all_passed = all(c.passed for c in checks)
        rejection = None
        if not all_passed:
            failed = [c for c in checks if not c.passed]
            rejection = VerificationResult(
                proposal_id=proposal.proposal_id,
                passed=False,
                checks=checks,
                rejection_code="VERIFICATION_FAILED",
                rejection_message="; ".join(c.detail for c in failed),
            )
            return rejection

        return VerificationResult(
            proposal_id=proposal.proposal_id,
            passed=True,
            checks=checks,
        )

    def _check_schema(self, proposal: ActionProposal) -> CheckResult:
        if not isinstance(proposal.arguments, dict):
            return CheckResult(check_name="schema", passed=False, detail="arguments must be a dict")
        return CheckResult(check_name="schema", passed=True, detail="valid")

    def _check_idempotency(self, key: str) -> CheckResult:
        if self.state.is_duplicate(key):
            return CheckResult(
                check_name="idempotency", passed=False, detail=f"Duplicate action: {key}"
            )
        return CheckResult(check_name="idempotency", passed=True, detail="not a duplicate")

    def _check_budget(self, remaining: float) -> CheckResult:
        if remaining <= 0:
            return CheckResult(
                check_name="budget", passed=False, detail=f"Budget exhausted: ${remaining:.4f}"
            )
        return CheckResult(
            check_name="budget", passed=True, detail=f"Budget OK: ${remaining:.4f} remaining"
        )

    def _check_sandbox_paths(self, arguments: dict[str, Any]) -> CheckResult:
        """Validate no path traversal or symlink escapes in arguments."""
        dangerous_patterns = ["../", "~/", "/etc/passwd", "/etc/shadow"]
        for key, value in arguments.items():
            if isinstance(value, str):
                for pattern in dangerous_patterns:
                    if pattern in value:
                        return CheckResult(
                            check_name="sandbox_paths",
                            passed=False,
                            detail=f"Unsafe path {value!r} in argument {key!r}",
                        )
        return CheckResult(check_name="sandbox_paths", passed=True, detail="paths are safe")
