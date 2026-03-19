"""Tests for the Hippocampus client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hippocampus.client import Hippocampus
from hippocampus.config import HippocampusConfig

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


class TestHippocampusInit:
    """Tests for Hippocampus initialization."""

    def test_init_with_default_config(self, fake_redis) -> None:
        mock_client = MagicMock()
        with patch(
            "hippocampus.client.EpisodicGraph"
        ) as mock_graph:
            mock_graph.return_value.redis = fake_redis
            hippo = Hippocampus(
                client=mock_client, agent_id="test_agent"
            )
            assert hippo.agent_id == "test_agent"
            assert hippo.config.redis_url == "redis://localhost:6379"

    def test_init_with_custom_config(self, fake_redis) -> None:
        mock_client = MagicMock()
        config = HippocampusConfig(
            redis_url="redis://custom:6379",
            max_guards=5,
        )
        with patch(
            "hippocampus.client.EpisodicGraph"
        ) as mock_graph:
            mock_graph.return_value.redis = fake_redis
            hippo = Hippocampus(
                client=mock_client,
                agent_id="test_agent",
                config=config,
            )
            assert hippo.config.max_guards == 5

    def test_chat_property_returns_proxy(self, fake_redis) -> None:
        mock_client = MagicMock()
        with patch(
            "hippocampus.client.EpisodicGraph"
        ) as mock_graph:
            mock_graph.return_value.redis = fake_redis
            hippo = Hippocampus(
                client=mock_client, agent_id="test_agent"
            )
            assert hippo.chat is not None
            assert hippo.chat.completions is not None


class TestHippocampusCreate:
    """Tests for the chat.completions.create() proxy."""

    def test_create_calls_openai_client(self, fake_redis) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response

        with patch(
            "hippocampus.client.EpisodicGraph"
        ) as mock_graph:
            mock_graph.return_value.redis = fake_redis
            mock_graph.return_value.get_recent_failures.return_value = []
            mock_graph.return_value.add_success.return_value = "action_123"

            hippo = Hippocampus(
                client=mock_client, agent_id="test_agent"
            )

            hippo.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": "Hello"},
                ],
            )

            # Should have called the underlying OpenAI client
            mock_client.chat.completions.create.assert_called_once()

    def test_create_calls_pre_inject_before_openai(
        self, fake_redis
    ) -> None:
        """Test that pre_inject is called before the OpenAI client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response

        with patch(
            "hippocampus.client.EpisodicGraph"
        ) as mock_graph:
            mock_graph.return_value.redis = fake_redis
            mock_graph.return_value.get_recent_failures.return_value = []
            mock_graph.return_value.add_success.return_value = "action_123"

            hippo = Hippocampus(
                client=mock_client, agent_id="test_agent"
            )

            call_order = []

            original_pre_inject = hippo.interceptor.pre_inject

            def track_pre_inject(*args, **kwargs):
                call_order.append("pre_inject")
                return original_pre_inject(*args, **kwargs)

            def track_openai(*args, **kwargs):
                call_order.append("openai")
                return mock_response

            with patch.object(
                hippo.interceptor,
                "pre_inject",
                side_effect=track_pre_inject,
            ):
                mock_client.chat.completions.create = MagicMock(
                    side_effect=track_openai
                )

                messages = [{"role": "user", "content": "hello"}]
                hippo.chat.completions.create(
                    messages=messages, model="gpt-4"
                )

                # Verify pre_inject called before openai
                assert call_order == ["pre_inject", "openai"]

    def test_create_calls_post_route_after_openai(
        self, fake_redis
    ) -> None:
        """Test that post_route is called after the OpenAI client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response

        with patch(
            "hippocampus.client.EpisodicGraph"
        ) as mock_graph:
            mock_graph.return_value.redis = fake_redis
            mock_graph.return_value.get_recent_failures.return_value = []
            mock_graph.return_value.add_success.return_value = "action_123"

            hippo = Hippocampus(
                client=mock_client, agent_id="test_agent"
            )

            call_order = []

            original_post_route = hippo.interceptor.post_route

            def track_openai(*args, **kwargs):
                call_order.append("openai")
                return mock_response

            def track_post_route(*args, **kwargs):
                call_order.append("post_route")
                return original_post_route(*args, **kwargs)

            mock_client.chat.completions.create = MagicMock(
                side_effect=track_openai
            )

            with patch.object(
                hippo.interceptor,
                "post_route",
                side_effect=track_post_route,
            ):
                messages = [{"role": "user", "content": "hello"}]
                hippo.chat.completions.create(
                    messages=messages, model="gpt-4"
                )

                # Verify openai called before post_route
                assert call_order == ["openai", "post_route"]

    def test_create_interceptor_methods_called(
        self, fake_redis
    ) -> None:
        """Test that both interceptor methods are called in create()."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response

        with patch(
            "hippocampus.client.EpisodicGraph"
        ) as mock_graph:
            mock_graph.return_value.redis = fake_redis
            mock_graph.return_value.get_recent_failures.return_value = []
            mock_graph.return_value.add_success.return_value = "action_123"

            hippo = Hippocampus(
                client=mock_client, agent_id="test_agent"
            )

            with patch.object(
                hippo.interceptor, "pre_inject", wraps=hippo.interceptor.pre_inject
            ) as mock_pre_inject, patch.object(
                hippo.interceptor,
                "post_route",
                wraps=hippo.interceptor.post_route,
            ) as mock_post_route:
                messages = [{"role": "user", "content": "test"}]
                hippo.chat.completions.create(
                    messages=messages, model="gpt-4"
                )

                # Both methods should be called
                mock_pre_inject.assert_called_once()
                mock_post_route.assert_called_once()
