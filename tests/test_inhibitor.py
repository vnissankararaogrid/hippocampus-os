"""Tests for the temporal inhibitor."""

from __future__ import annotations

import pytest

from hippocampus.config import HippocampusConfig
from hippocampus.graph import EpisodicGraph
from hippocampus.inhibitor import TemporalInhibitor

try:
    import fakeredis

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False


@pytest.fixture
def fake_redis():
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def graph(fake_redis):
    g = EpisodicGraph(agent_id="test_agent", redis_client=fake_redis)
    yield g
    g.clear()


@pytest.fixture
def inhibitor(graph):
    return TemporalInhibitor(graph=graph)


class TestTemporalInhibitor:
    """Tests for TemporalInhibitor.get_relevant_guards()."""

    def test_high_relevance_always_injected(
        self, inhibitor: TemporalInhibitor, graph: EpisodicGraph
    ) -> None:
        """Recent failures (high relevance) should always be injected."""
        graph.add_failure(
            agent_id="test_agent",
            intent="Test",
            action="test_action",
            error="auth_expired",
            error_detail="403",
        )
        guards = inhibitor.get_relevant_guards(
            user_message="Do something unrelated", agent_id="test_agent"
        )
        assert len(guards) >= 1
        assert guards[0]["error_type"] == "auth_expired"

    def test_no_failures_returns_empty(
        self, inhibitor: TemporalInhibitor
    ) -> None:
        """No failures in graph = no guards returned."""
        guards = inhibitor.get_relevant_guards(
            user_message="Hello", agent_id="test_agent"
        )
        assert guards == []

    def test_custom_config_thresholds(
        self, graph: EpisodicGraph
    ) -> None:
        """Custom config thresholds should be respected."""
        config = HippocampusConfig(
            high_relevance=0.8,
            medium_relevance=0.5,
        )
        inhibitor = TemporalInhibitor(graph=graph, config=config)
        assert inhibitor.config.high_relevance == 0.8
        assert inhibitor.config.medium_relevance == 0.5
