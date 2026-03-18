"""Tests for the interceptor pipeline orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hippocampus.compiler import StateGuardCompiler
from hippocampus.config import HippocampusConfig
from hippocampus.graph import EpisodicGraph
from hippocampus.inhibitor import TemporalInhibitor
from hippocampus.interceptor import Interceptor
from hippocampus.router import FailureType, StateRouter

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
def pipeline(fake_redis):
    """Provide a fully wired interceptor pipeline with fake Redis."""
    graph = EpisodicGraph(agent_id="test_agent", redis_client=fake_redis)
    router = StateRouter()
    compiler = StateGuardCompiler(max_guards=3)
    config = HippocampusConfig()
    inhibitor = TemporalInhibitor(graph=graph, config=config)

    interceptor = Interceptor(
        graph=graph,
        router=router,
        compiler=compiler,
        inhibitor=inhibitor,
        config=config,
    )
    yield interceptor, graph
    graph.clear()


class TestInterceptorPreInject:
    """Tests for Interceptor.pre_inject()."""

    def test_no_failures_no_injection(
        self, pipeline: tuple
    ) -> None:
        interceptor, graph = pipeline
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        result = interceptor.pre_inject(messages, agent_id="test_agent")
        assert len(result) == 2
        assert "<CONTEXT_ENGINEERING>" not in result[0]["content"]

    def test_with_failure_injects_guard(
        self, pipeline: tuple
    ) -> None:
        interceptor, graph = pipeline
        # Add a failure to the graph
        graph.add_failure(
            agent_id="test_agent",
            intent="Query Salesforce",
            action="salesforce_query(data)",
            error="auth_expired",
            error_detail="403 Forbidden",
        )
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Query Salesforce again"},
        ]
        result = interceptor.pre_inject(messages, agent_id="test_agent")
        # Should have State Guard injected into system message
        assert "<CONTEXT_ENGINEERING>" in result[0]["content"]
        assert "auth_expired" in result[0]["content"]

    def test_inject_creates_system_if_missing(
        self, pipeline: tuple
    ) -> None:
        interceptor, graph = pipeline
        graph.add_failure(
            agent_id="test_agent",
            intent="Test",
            action="test_action",
            error="server_error",
            error_detail="500",
        )
        messages = [
            {"role": "user", "content": "Try again"},
        ]
        result = interceptor.pre_inject(messages, agent_id="test_agent")
        # Should create a system message at position 0
        assert result[0]["role"] == "system"
        assert "<CONTEXT_ENGINEERING>" in result[0]["content"]

    def test_original_messages_not_mutated(
        self, pipeline: tuple
    ) -> None:
        interceptor, graph = pipeline
        graph.add_failure(
            agent_id="test_agent",
            intent="Test",
            action="test_action",
            error="rate_limited",
            error_detail="429",
        )
        messages = [
            {"role": "system", "content": "Original system prompt"},
            {"role": "user", "content": "Hello"},
        ]
        result = interceptor.pre_inject(messages, agent_id="test_agent")
        # Original messages should be unchanged
        assert messages[0]["content"] == "Original system prompt"
        # Result should have modified content
        assert "<CONTEXT_ENGINEERING>" in result[0]["content"]


class TestInterceptorPostRoute:
    """Tests for Interceptor.post_route()."""

    def test_failure_response_stored(
        self, pipeline: tuple
    ) -> None:
        interceptor, graph = pipeline
        messages = [
            {"role": "user", "content": "Query Salesforce"},
        ]
        result = interceptor.post_route(
            content="403 Forbidden - Authentication expired",
            tool_calls=None,
            original_messages=messages,
            agent_id="test_agent",
        )
        assert result.is_failure is True
        assert result.error_type == FailureType.AUTH_EXPIRED
        # Should be stored in graph
        failures = graph.get_recent_failures(limit=5)
        assert len(failures) >= 1

    def test_success_response_stored(
        self, pipeline: tuple
    ) -> None:
        interceptor, graph = pipeline
        messages = [
            {"role": "user", "content": "Get data"},
        ]
        result = interceptor.post_route(
            content="Here is the data you requested: {'status': 'ok'}",
            tool_calls=None,
            original_messages=messages,
            agent_id="test_agent",
        )
        assert result.is_success is True
