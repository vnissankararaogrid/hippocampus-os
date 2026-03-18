"""Custom exceptions for Hippocampus OS."""

from __future__ import annotations


class HippocampusError(Exception):
    """Base exception for all Hippocampus OS errors."""


class RoutingError(HippocampusError):
    """Raised when failure classification fails."""


class GraphError(HippocampusError):
    """Raised when episodic graph operations fail."""


class CompilationError(HippocampusError):
    """Raised when State Guard compilation fails."""


class InjectionError(HippocampusError):
    """Raised when context injection fails."""
