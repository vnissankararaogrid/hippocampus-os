"""Tests for SDK configuration."""

from __future__ import annotations

import os

from hippocampus.config import HippocampusConfig


class TestHippocampusConfig:
    """Tests for HippocampusConfig."""

    def test_default_values(self) -> None:
        config = HippocampusConfig()
        assert config.redis_url == "redis://localhost:6379"
        assert config.default_ttl == 86400
        assert config.max_guards == 3
        assert config.inhibition_threshold == 0.1
        assert config.high_relevance == 0.5
        assert config.medium_relevance == 0.2

    def test_custom_values(self) -> None:
        config = HippocampusConfig(
            redis_url="redis://custom:6379",
            max_guards=5,
            default_ttl=3600,
        )
        assert config.redis_url == "redis://custom:6379"
        assert config.max_guards == 5
        assert config.default_ttl == 3600

    def test_env_override(self) -> None:
        os.environ["HIPPORC_REDIS_URL"] = "redis://env:6379"
        try:
            config = HippocampusConfig()
            assert config.redis_url == "redis://env:6379"
        finally:
            del os.environ["HIPPORC_REDIS_URL"]
