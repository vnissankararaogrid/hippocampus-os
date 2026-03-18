"""SDK configuration with validated settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class HippocampusConfig(BaseSettings):
    """Configuration for Hippocampus OS.

    All settings can be overridden via environment variables
    with the HIPPORC_ prefix. Example: HIPPORC_REDIS_URL=redis://...

    Attributes:
        redis_url: Redis connection string.
        default_ttl: Time-to-live for episodic nodes in seconds.
        max_guards: Maximum State Guards injected per call.
        inhibition_threshold: Relevance below this = suppress memory.
        high_relevance: Relevance above this = always inject.
        medium_relevance: Relevance above this = inject if related.
    """

    redis_url: str = "redis://localhost:6379"
    default_ttl: int = 86400  # 24 hours
    max_guards: int = 3
    inhibition_threshold: float = 0.1
    high_relevance: float = 0.5
    medium_relevance: float = 0.2

    model_config = {"env_prefix": "HIPPORC_"}
