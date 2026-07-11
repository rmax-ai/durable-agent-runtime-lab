"""Tests for ModelRouter — role routing and error handling."""

from __future__ import annotations

import pytest

from durable_agent_runtime.models.base import MockProvider
from durable_agent_runtime.models.router import ModelRouter


@pytest.fixture
def mock_advisor():
    return MockProvider(name="advisor")


@pytest.fixture
def mock_planner():
    return MockProvider(name="planner")


@pytest.fixture
def mock_worker():
    return MockProvider(name="worker")


@pytest.fixture
def router(mock_advisor, mock_planner, mock_worker):
    return ModelRouter(
        advisor=mock_advisor,
        planner=mock_planner,
        worker=mock_worker,
    )


class TestModelRouter:
    """Tests for ModelRouter role-based routing."""

    def test_get_advisor(self, router: ModelRouter, mock_advisor: MockProvider):
        """Verify advisor slot returns the correct provider."""
        provider = router.get_provider("advisor")
        assert provider is mock_advisor
        assert provider.name == "advisor"

    def test_get_planner(self, router: ModelRouter, mock_planner: MockProvider):
        """Verify planner slot returns the correct provider."""
        provider = router.get_provider("planner")
        assert provider is mock_planner
        assert provider.name == "planner"

    def test_get_worker(self, router: ModelRouter, mock_worker: MockProvider):
        """Verify worker slot returns the correct provider."""
        provider = router.get_provider("worker")
        assert provider is mock_worker
        assert provider.name == "worker"

    def test_unknown_role_raises_error(self, router: ModelRouter):
        """Verify unknown role raises ValueError with informative message."""
        with pytest.raises(ValueError) as exc_info:
            router.get_provider("unknown")
        error_msg = str(exc_info.value)
        assert "unknown" in error_msg
        assert "advisor" in error_msg
        assert "planner" in error_msg
        assert "worker" in error_msg

    def test_unknown_role_empty_string(self, router: ModelRouter):
        """Verify empty string role raises ValueError."""
        with pytest.raises(ValueError):
            router.get_provider("")

    def test_provider_can_be_same_instance(self):
        """Verify the same provider can fill all three roles."""
        shared = MockProvider(name="shared")
        router = ModelRouter(advisor=shared, planner=shared, worker=shared)
        assert router.get_provider("advisor") is shared
        assert router.get_provider("planner") is shared
        assert router.get_provider("worker") is shared

    def test_providers_are_independent_references(self, router: ModelRouter):
        """Verify each role holds an independent provider reference."""
        assert router.get_provider("advisor") is not router.get_provider("planner")
        assert router.get_provider("planner") is not router.get_provider("worker")

    def test_call_count_independence(self, router: ModelRouter):
        """Verify calls to one provider don't affect another's call count."""
        # All start at 0
        assert router.get_provider("advisor").call_count == 0
        assert router.get_provider("planner").call_count == 0
        assert router.get_provider("worker").call_count == 0
