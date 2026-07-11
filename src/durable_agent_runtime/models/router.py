"""Model router — role-based routing between model providers (Section 6.11).

Supports three model roles: advisor, planner, worker.
The same underlying provider can fill multiple roles.
"""

from __future__ import annotations

from durable_agent_runtime.models.base import ModelProvider

VALID_ROLES = frozenset({"advisor", "planner", "worker"})


class ModelRouter:
    """Routes tasks to model providers by role.

    Example:
        router = ModelRouter(advisor=cheap_model, planner=smart_model, worker=cheap_model)
        provider = router.get_provider("planner")  # returns smart_model
    """

    def __init__(
        self,
        advisor: ModelProvider,
        planner: ModelProvider,
        worker: ModelProvider,
    ) -> None:
        self._providers: dict[str, ModelProvider] = {
            "advisor": advisor,
            "planner": planner,
            "worker": worker,
        }

    def get_provider(self, role: str) -> ModelProvider:
        """Get the model provider for the given role.

        Args:
            role: One of "advisor", "planner", "worker".

        Returns:
            The ModelProvider assigned to that role.

        Raises:
            ValueError: If the role is unknown.
        """
        if role not in self._providers:
            valid = sorted(VALID_ROLES)
            raise ValueError(f"Unknown model role: '{role}'. Valid roles: {valid}")
        return self._providers[role]
