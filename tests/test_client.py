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
