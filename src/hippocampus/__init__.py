"""Hippocampus OS — Brain-mimetic context compiler for AI agents.

Wraps any OpenAI-compatible client and injects state-aware
context guards to prevent infinite agent loops.
"""

from __future__ import annotations

from .config import HippocampusConfig

__version__ = "0.1.0"

__all__ = ["HippocampusConfig"]

# Public API will be exported here after implementation:
# from .client import Hippocampus
