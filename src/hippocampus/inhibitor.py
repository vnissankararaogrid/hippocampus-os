"""Temporal inhibitor — decides which memories reach the LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import HippocampusConfig

if TYPE_CHECKING:
    from .graph import EpisodicGraph


class TemporalInhibitor:
    """Filters episodic memories by temporal relevance.

    Inhibition is as important as injection: not all context
    should reach the LLM. Old failures decay. Irrelevant facts
    are suppressed.

    Three-tier logic:
    - High relevance (≥0.5): ALWAYS inject
    - Medium relevance (≥0.2): Inject if error type in user message
    - Low relevance (<0.2): INHIBIT (suppress)

    Args:
        graph: The episodic graph to query.
        config: Configuration with relevance thresholds.
    """

    def __init__(
        self,
        graph: EpisodicGraph,
        config: HippocampusConfig | None = None,
    ) -> None:
        self.graph = graph
        self.config = config or HippocampusConfig()

    def get_relevant_guards(
        self, user_message: str, agent_id: str
    ) -> list[dict]:
        """Get failures relevant to the current conversation.

        Applies temporal inhibition logic to filter out
        irrelevant or decayed memories.

        Args:
            user_message: The current user message text.
            agent_id: The agent identifier to query failures for.

        Returns:
            List of failure dicts that pass the inhibition filter.
        """
        failures = self.graph.get_recent_failures(limit=10)

        active_failures: list[dict] = []
        for f in failures:
            relevance = f.get("relevance", 0.0)

            if relevance >= self.config.high_relevance:
                # High relevance: always inject regardless of topic
                active_failures.append(f)
            elif relevance >= self.config.medium_relevance:
                # Medium relevance: inject if error type in user message
                error_words = f.get("error_type", "").replace("_", " ")
                if error_words in user_message.lower():
                    active_failures.append(f)
            # else: INHIBIT — don't inject low-relevance failures

        return active_failures
