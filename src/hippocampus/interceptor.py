"""Interceptor — orchestrates the 6-stage context engineering pipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .config import HippocampusConfig
from .exceptions import InjectionError

if TYPE_CHECKING:
    from .compiler import StateGuardCompiler
    from .graph import EpisodicGraph
    from .inhibitor import TemporalInhibitor
    from .router import RouteResult, StateRouter

logger = logging.getLogger(__name__)


class Interceptor:
    """Orchestrates the context engineering pipeline.

    Stages:
    1. Pre-inject: query graph → inhibit → compile → inject
    2. Post-route: route response → store result

    Args:
        graph: The episodic graph for failure storage.
        router: The state router for failure classification.
        compiler: The State Guard compiler.
        inhibitor: The temporal inhibitor.
        config: SDK configuration.
    """

    def __init__(
        self,
        graph: EpisodicGraph,
        router: StateRouter,
        compiler: StateGuardCompiler,
        inhibitor: TemporalInhibitor,
        config: HippocampusConfig | None = None,
    ) -> None:
        self.graph = graph
        self.router = router
        self.compiler = compiler
        self.inhibitor = inhibitor
        self.config = config or HippocampusConfig()

    def pre_inject(
        self, messages: list[dict], agent_id: str
    ) -> list[dict]:
        """Inject State Guards into messages before LLM call.

        Pipeline: query graph → inhibit → compile → inject at pos 0.

        Args:
            messages: The message list from the user's kwargs.
            agent_id: The agent identifier.

        Returns:
            Modified messages with State Guards injected.
            Original messages if no relevant failures exist.
        """
        # Extract last user message for relevance matching
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        # Query episodic graph for relevant failures
        state_guards = self.inhibitor.get_relevant_guards(
            user_message=user_message, agent_id=agent_id
        )

        if not state_guards:
            logger.debug("No relevant guards to inject")
            return messages

        # Compile failures into XML
        guard_xml = self.compiler.compile(state_guards)
        if not guard_xml:
            return messages

        # Inject at position 0 of system prompt
        try:
            modified = [msg.copy() for msg in messages]
            system_found = False
            for i, msg in enumerate(modified):
                if msg.get("role") == "system":
                    modified[i] = {
                        **msg,
                        "content": guard_xml + "\n" + msg.get("content", ""),
                    }
                    system_found = True
                    break

            if not system_found:
                modified.insert(
                    0, {"role": "system", "content": guard_xml}
                )

            logger.info(
                "Injected %d State Guard(s) for agent %s",
                len(state_guards),
                agent_id,
            )
            return modified

        except Exception as exc:
            raise InjectionError(
                f"Failed to inject State Guards: {exc}"
            ) from exc

    def post_route(
        self,
        content: str,
        tool_calls: list | None,
        original_messages: list[dict],
        agent_id: str,
    ) -> RouteResult:
        """Route the LLM response and store the result.

        Pipeline: route content → store failure/success in graph.

        Args:
            content: The LLM response text content.
            tool_calls: Any tool calls from the response.
            original_messages: The original messages (for intent extraction).
            agent_id: The agent identifier.

        Returns:
            RouteResult from the classifier.
        """
        route_result = self.router.route(content)

        # Extract intent from last user message
        intent = ""
        for msg in reversed(original_messages):
            if msg.get("role") == "user":
                intent = msg.get("content", "")[:200]
                break

        # Determine action description
        action = (
            str(tool_calls)[:500]
            if tool_calls
            else content[:500]
        )

        if route_result.is_failure:
            self.graph.add_failure(
                agent_id=agent_id,
                intent=intent,
                action=action,
                error=route_result.error_type.value
                if route_result.error_type
                else "unknown",
                error_detail=route_result.detail,
            )
            logger.info(
                "Stored failure: %s for agent %s",
                route_result.error_type,
                agent_id,
            )
        elif route_result.is_success:
            self.graph.add_success(
                agent_id=agent_id,
                intent=intent,
                action=action,
            )

        return route_result
