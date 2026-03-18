"""Tests for the episodic graph (Redis-backed)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from hippocampus.graph import EpisodicGraph, EpisodicNode

# Use fakeredis for unit tests — no real Redis needed
try:
    import fakeredis

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False


@pytest.fixture
def fake_redis():
    """Provide a fake Redis client for testing."""
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def graph(fake_redis):
    """Provide an EpisodicGraph with fake Redis."""
    g = EpisodicGraph(
        agent_id="test_agent",
        redis_client=fake_redis,
    )
    yield g
    g.clear()


class TestEpisodicNode:
    """Tests for the EpisodicNode dataclass."""

    def test_fresh_node_not_expired(self) -> None:
        node = EpisodicNode(
            node_id="fail_abc123",
            agent_id="test",
            node_type="fail",
            content="Auth expired",
            timestamp=time.time(),
        )
        assert node.is_expired is False
        assert node.relevance_score > 0.5

    def test_old_node_is_expired(self) -> None:
        node = EpisodicNode(
            node_id="fail_old",
            agent_id="test",
            node_type="fail",
            content="Auth expired",
            timestamp=time.time() - 86400 * 7,  # 7 days old
        )
        assert node.is_expired is True
        assert node.relevance_score < 0.05


class TestEpisodicGraphAddFailure:
    """Tests for EpisodicGraph.add_failure()."""

    def test_add_failure_returns_fail_id(self, graph: EpisodicGraph) -> None:
        fail_id = graph.add_failure(
            agent_id="test_agent",
            intent="Pull Q3 revenue",
            action="salesforce_query(Q3_Revenue)",
            error="auth_expired",
            error_detail="403 Forbidden - Authentication expired",
        )
        assert fail_id.startswith("fail_")

    def test_add_failure_stores_in_recent_failures(
        self, graph: EpisodicGraph
    ) -> None:
        graph.add_failure(
            agent_id="test_agent",
            intent="Pull Q3 revenue",
            action="salesforce_query(Q3_Revenue)",
            error="auth_expired",
            error_detail="403 Forbidden",
        )
        failures = graph.get_recent_failures(limit=5)
        assert len(failures) == 1
        assert failures[0]["error_type"] == "auth_expired"

    def test_add_multiple_failures(self, graph: EpisodicGraph) -> None:
        for i in range(5):
            graph.add_failure(
                agent_id="test_agent",
                intent=f"Intent {i}",
                action=f"action_{i}",
                error="rate_limited",
                error_detail=f"Attempt {i}",
            )
        failures = graph.get_recent_failures(limit=3)
        assert len(failures) == 3


class TestEpisodicGraphAddSuccess:
    """Tests for EpisodicGraph.add_success()."""

    def test_add_success_returns_action_id(
        self, graph: EpisodicGraph
    ) -> None:
        action_id = graph.add_success(
            agent_id="test_agent",
            intent="Pull Q3 revenue",
            action="salesforce_query(Q3_Revenue)",
        )
        assert action_id.startswith("action_")

    def test_success_does_not_appear_in_failures(
        self, graph: EpisodicGraph
    ) -> None:
        graph.add_success(
            agent_id="test_agent",
            intent="Pull Q3 revenue",
            action="salesforce_query(Q3_Revenue)",
        )
        failures = graph.get_recent_failures(limit=10)
        assert len(failures) == 0


class TestEpisodicGraphCheckAction:
    """Tests for EpisodicGraph.check_action_failed_recently()."""

    def test_check_failed_action_returns_failure(
        self, graph: EpisodicGraph
    ) -> None:
        graph.add_failure(
            agent_id="test_agent",
            intent="Pull data",
            action="salesforce_query(data)",
            error="auth_expired",
            error_detail="403",
        )
        result = graph.check_action_failed_recently("salesforce_query(data)")
        assert result is not None
        assert result["error_type"] == "auth_expired"

    def test_check_non_failed_action_returns_none(
        self, graph: EpisodicGraph
    ) -> None:
        result = graph.check_action_failed_recently("nonexistent_action")
        assert result is None


class TestEpisodicGraphClear:
    """Tests for EpisodicGraph.clear()."""

    def test_clear_removes_all_data(self, graph: EpisodicGraph) -> None:
        graph.add_failure(
            agent_id="test_agent",
            intent="Test",
            action="test_action",
            error="server_error",
            error_detail="500",
        )
        graph.clear()
        failures = graph.get_recent_failures(limit=10)
        assert len(failures) == 0
