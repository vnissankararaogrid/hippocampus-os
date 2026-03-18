"""Redis-backed episodic memory graph for agent failures."""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

import redis

from .exceptions import GraphError


@dataclass
class EpisodicNode:
    """A single episode in the agent's experience.

    Attributes:
        node_id: Unique identifier (e.g., "fail_a1b2c3d4e5f6").
        agent_id: The agent this episode belongs to.
        node_type: One of "intent", "action", "result", "fail".
        content: The text content of this episode.
        timestamp: Unix epoch seconds when created.
        relevance_score: Decay-based relevance (1.0 = fresh, 0.01 = decayed).
        ttl_seconds: Time-to-live in seconds.
    """

    node_id: str
    agent_id: str
    node_type: str  # "intent", "action", "result", "fail"
    content: str
    timestamp: float = field(default_factory=time.time)
    relevance_score: float = 1.0
    ttl_seconds: int = 86400

    @property
    def is_expired(self) -> bool:
        """Check if this node has decayed below relevance threshold."""
        age_hours = (time.time() - self.timestamp) / 3600
        self.relevance_score = max(0.01, pow(2.718, -0.5 * age_hours))
        return self.relevance_score < 0.05


@dataclass
class EpisodicEdge:
    """A directed edge between episodic nodes.

    Attributes:
        from_node: Source node ID.
        to_node: Target node ID.
        edge_type: "ATTEMPTED_WITH", "FAILED_WITH", or "SUCCEEDED_WITH".
        timestamp: Unix epoch seconds when created.
    """

    from_node: str
    to_node: str
    edge_type: str
    timestamp: float = field(default_factory=time.time)


class EpisodicGraph:
    """Redis-backed episodic memory graph.

    Uses Redis hashes for nodes and Redis sets for edges.
    Recent failures are stored in a sorted set for fast retrieval.
    All data has TTL-based expiration.

    Args:
        agent_id: Unique identifier for the agent.
        redis_url: Redis connection string.
        redis_client: Optional pre-configured Redis client (for testing).
    """

    def __init__(
        self,
        agent_id: str,
        redis_url: str = "redis://localhost:6379",
        redis_client: redis.Redis | None = None,
    ):
        self.agent_id = agent_id
        if redis_client is not None:
            self.redis = redis_client
        else:
            self.redis = redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = f"hippo:{agent_id}"

    def _node_key(self, node_id: str) -> str:
        return f"{self._key_prefix}:node:{node_id}"

    def _edges_key(self, node_id: str) -> str:
        return f"{self._key_prefix}:edges:{node_id}"

    def _failures_key(self) -> str:
        return f"{self._key_prefix}:recent_failures"

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def add_failure(
        self,
        agent_id: str,
        intent: str,
        action: str,
        error: str,
        error_detail: str = "",
    ) -> str:
        """Store a complete failure episode: INTENT → ACTION → FAIL.

        Args:
            agent_id: The agent that experienced the failure.
            intent: The user's original intent (truncated to 200 chars).
            action: The action that was attempted.
            error: The error type (e.g., "auth_expired").
            error_detail: Additional error detail text.

        Returns:
            The node_id of the created fail node.

        Raises:
            GraphError: If Redis operations fail.
        """
        try:
            intent_id = f"intent_{self._hash(intent)}"
            action_id = f"action_{self._hash(action)}"
            fail_id = f"fail_{self._hash(error + action)}"

            pipe = self.redis.pipeline()

            nodes = [
                (intent_id, "intent", intent[:200]),
                (action_id, "action", action[:500]),
                (fail_id, "fail", f"{error}: {error_detail[:200]}"),
            ]

            for node_id, ntype, content in nodes:
                node = EpisodicNode(
                    node_id=node_id,
                    agent_id=agent_id,
                    node_type=ntype,
                    content=content,
                )
                pipe.hset(self._node_key(node_id), mapping=asdict(node))
                pipe.expire(self._node_key(node_id), 86400)

            pipe.sadd(
                self._edges_key(intent_id), f"{action_id}:ATTEMPTED_WITH"
            )
            pipe.sadd(
                self._edges_key(action_id), f"{fail_id}:FAILED_WITH"
            )

            pipe.zadd(
                self._failures_key(),
                {f"{action_id}|{error}|{error_detail[:100]}": time.time()},
            )
            pipe.zremrangebyrank(self._failures_key(), 0, -101)

            pipe.execute()
            return fail_id

        except redis.RedisError as exc:
            raise GraphError(f"Failed to store failure episode: {exc}") from exc

    def add_success(
        self, agent_id: str, intent: str, action: str
    ) -> str:
        """Store a success episode: INTENT → ACTION → SUCCESS.

        Args:
            agent_id: The agent that succeeded.
            intent: The user's original intent.
            action: The action that succeeded.

        Returns:
            The node_id of the created action node.

        Raises:
            GraphError: If Redis operations fail.
        """
        try:
            intent_id = f"intent_{self._hash(intent)}"
            action_id = f"action_{self._hash(action)}"

            pipe = self.redis.pipeline()

            for node_id, ntype, content in [
                (intent_id, "intent", intent[:200]),
                (action_id, "action", action[:500]),
            ]:
                node = EpisodicNode(
                    node_id=node_id,
                    agent_id=agent_id,
                    node_type=ntype,
                    content=content,
                )
                pipe.hset(self._node_key(node_id), mapping=asdict(node))
                pipe.expire(self._node_key(node_id), 86400)

            pipe.sadd(
                self._edges_key(intent_id), f"{action_id}:SUCCEEDED_WITH"
            )
            pipe.execute()
            return action_id

        except redis.RedisError as exc:
            raise GraphError(f"Failed to store success episode: {exc}") from exc

    def get_recent_failures(self, limit: int = 5) -> list[dict]:
        """Get most recent failures, sorted by time with relevance.

        Only returns failures with relevance_score > inhibition_threshold.

        Args:
            limit: Maximum number of failures to return.

        Returns:
            List of failure dicts with action, error_type, detail,
            timestamp, and relevance score.
        """
        raw = self.redis.zrevrange(
            self._failures_key(), 0, limit - 1, withscores=True
        )
        failures: list[dict] = []
        for entry, score in raw:
            parts = entry.split("|")
            age_hours = (time.time() - score) / 3600
            relevance = max(0.01, pow(2.718, -0.5 * age_hours))

            if relevance > 0.1:
                failures.append(
                    {
                        "action": parts[0] if len(parts) > 0 else "unknown",
                        "error_type": (
                            parts[1] if len(parts) > 1 else "unknown"
                        ),
                        "detail": parts[2] if len(parts) > 2 else "",
                        "timestamp": score,
                        "relevance": round(relevance, 2),
                    }
                )
        return failures

    def check_action_failed_recently(self, action: str) -> Optional[dict]:
        """Check if a specific action failed recently.

        THE key query for loop prevention: "Did the action I'm about
        to take just fail?"

        Args:
            action: The action string to check.

        Returns:
            Failure dict if the action failed recently, None otherwise.
        """
        failures = self.get_recent_failures(limit=20)
        action_hash = self._hash(action)
        for f in failures:
            if action_hash in f["action"]:
                return f
        return None

    def clear(self) -> None:
        """Wipe all episodic memory for this agent."""
        pattern = f"{self._key_prefix}:*"
        for key in self.redis.scan_iter(pattern):
            self.redis.delete(key)
