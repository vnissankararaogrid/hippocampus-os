"""Hippocampus — the main user-facing SDK wrapper."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .compiler import StateGuardCompiler

if TYPE_CHECKING:
    from openai import OpenAI
from .config import HippocampusConfig
from .graph import EpisodicGraph
from .inhibitor import TemporalInhibitor
from .interceptor import Interceptor
from .router import StateRouter

logger = logging.getLogger(__name__)


class Hippocampus:
    """Brain-mimetic context compiler for AI agents.

    Wraps any OpenAI-compatible client and injects state-aware
    context guards to prevent infinite agent loops.

    Usage:
        from openai import OpenAI
        from hippocampus import Hippocampus

        raw_client = OpenAI()
        client = Hippocampus(raw_client, agent_id="my_agent")

        # Drop-in replacement — same API as OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}]
        )

    Args:
        client: An OpenAI client instance to wrap.
        agent_id: Unique identifier for this agent.
        config: Optional SDK configuration.
    """

    def __init__(
        self,
        client: OpenAI,
        agent_id: str,
        config: HippocampusConfig | None = None,
    ) -> None:
        self._client = client
        self.agent_id = agent_id
        self.config = config or HippocampusConfig()

        # Initialize context engineering pipeline components
        self.graph = EpisodicGraph(
            agent_id=agent_id,
            redis_url=self.config.redis_url,
        )
        self.router = StateRouter()
        self.compiler = StateGuardCompiler(
            max_guards=self.config.max_guards,
        )
        self.inhibitor = TemporalInhibitor(
            graph=self.graph,
            config=self.config,
        )
        self.interceptor = Interceptor(
            graph=self.graph,
            router=self.router,
            compiler=self.compiler,
            inhibitor=self.inhibitor,
            config=self.config,
        )

    @property
    def chat(self) -> _ChatProxy:
        """Mimics openai.chat for drop-in replacement."""
        return _ChatProxy(self)


class _ChatProxy:
    """Proxy for the chat namespace."""

    def __init__(self, hippocampus: Hippocampus) -> None:
        self._hippocampus = hippocampus
        self.completions = _CompletionsProxy(hippocampus)


class _CompletionsProxy:
    """Proxy for chat.completions that intercepts create() calls."""

    def __init__(self, hippocampus: Hippocampus) -> None:
        self._h = hippocampus

    def create(self, **kwargs) -> object:
        """Intercept, compile context, call LLM, store episodic.

        This is the main entry point. It:
        1. Queries episodic graph for relevant failures
        2. Injects State Guards at position 0 of system prompt
        3. Calls the actual OpenAI client
        4. Routes the response and stores failure/success

        Args:
            **kwargs: All arguments passed to openai.chat.completions.create()

        Returns:
            Unmodified OpenAI response object.
        """
        h = self._h

        # STEP 1: Pre-inject State Guards
        messages = kwargs.get("messages", [])
        modified_messages = h.interceptor.pre_inject(
            messages=messages, agent_id=h.agent_id
        )
        kwargs["messages"] = modified_messages

        # STEP 2: Call the actual LLM
        response = h._client.chat.completions.create(**kwargs)

        # STEP 3: Post-route the response
        if response.choices:
            content = response.choices[0].message.content or ""
            tool_calls = response.choices[0].message.tool_calls

            h.interceptor.post_route(
                content=content,
                tool_calls=tool_calls,
                original_messages=messages,
                agent_id=h.agent_id,
            )

        return response
