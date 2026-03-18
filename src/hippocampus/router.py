"""Tier 1 deterministic failure classification router."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FailureType(Enum):
    """Classified failure types for agent responses."""

    AUTH_EXPIRED = "auth_expired"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    SERVER_ERROR = "server_error"
    PERMISSION_DENIED = "permission_denied"
    VALIDATION_ERROR = "validation_error"
    APOLOGY_LOOP = "apology_loop"
    NONE = "none"


@dataclass
class RouteResult:
    """Result of routing an LLM response through the classifier."""

    is_failure: bool
    is_success: bool
    error_type: FailureType | None
    detail: str

    @property
    def severity(self) -> str:
        """Return severity level based on error type."""
        if self.error_type in (
            FailureType.AUTH_EXPIRED,
            FailureType.PERMISSION_DENIED,
        ):
            return "critical"
        if self.error_type in (
            FailureType.RATE_LIMITED,
            FailureType.SERVER_ERROR,
        ):
            return "high"
        return "medium"


# Deterministic patterns — no LLM needed, <5ms
PATTERNS: dict[FailureType, list[re.Pattern[str]]] = {
    FailureType.AUTH_EXPIRED: [
        re.compile(r"40[13]\s*(forbidden|unauthorized|auth)", re.I),
        re.compile(r"auth.*expir", re.I),
        re.compile(r"token.*invalid|invalid.*token", re.I),
        re.compile(r"credentials.*expired|expired.*credentials", re.I),
    ],
    FailureType.RATE_LIMITED: [
        re.compile(r"429\s*(too many|rate limit)", re.I),
        re.compile(r"rate.?limit", re.I),
        re.compile(r"too many requests", re.I),
    ],
    FailureType.NOT_FOUND: [
        re.compile(r"404\s*not found", re.I),
        re.compile(r"resource.*not found|not found.*resource", re.I),
    ],
    FailureType.SERVER_ERROR: [
        re.compile(r"5\d{2}\s*(server|internal|error)", re.I),
        re.compile(r"internal server error", re.I),
    ],
    FailureType.APOLOGY_LOOP: [
        re.compile(r"I'm sorry.{0,30}(I can't|I'm unable|I failed)", re.I),
        re.compile(r"(sorry|apologize).{0,50}(sorry|apologize)", re.I),
        re.compile(r"let me try again.{0,20}let me try again", re.I),
    ],
    FailureType.PERMISSION_DENIED: [
        re.compile(r"403\s*forbidden", re.I),
        re.compile(r"permission.*denied|denied.*permission", re.I),
        re.compile(r"access.*denied|denied.*access", re.I),
    ],
    FailureType.VALIDATION_ERROR: [
        re.compile(r"422\s*(unprocessable|validation)", re.I),
        re.compile(r"validation.*error|invalid.*input", re.I),
    ],
}


class StateRouter:
    """Tier 1: Deterministic failure classification.

    Handles 80% of failure detection with regex patterns.
    Latency: <5ms. Zero token cost.
    """

    def route(self, content: str) -> RouteResult:
        """Classify LLM response content for failures.

        Args:
            content: The text content of the LLM response.

        Returns:
            RouteResult indicating failure type and severity.
        """
        if not content:
            return RouteResult(
                is_failure=False,
                is_success=True,
                error_type=None,
                detail="Empty response",
            )

        for failure_type, patterns in PATTERNS.items():
            for pattern in patterns:
                if pattern.search(content):
                    return RouteResult(
                        is_failure=True,
                        is_success=False,
                        error_type=failure_type,
                        detail=content[:200],
                    )

        return RouteResult(
            is_failure=False,
            is_success=True,
            error_type=None,
            detail=content[:200],
        )

    def route_tool_result(self, status_code: int, body: str) -> RouteResult:
        """Classify HTTP tool results by status code.

        Even faster than text routing — direct status code mapping.

        Args:
            status_code: HTTP status code from tool call.
            body: Response body text.

        Returns:
            RouteResult indicating failure type.
        """
        if status_code in (401, 403):
            return RouteResult(True, False, FailureType.AUTH_EXPIRED, body[:200])
        if status_code == 429:
            return RouteResult(True, False, FailureType.RATE_LIMITED, body[:200])
        if status_code == 404:
            return RouteResult(True, False, FailureType.NOT_FOUND, body[:200])
        if status_code >= 500:
            return RouteResult(True, False, FailureType.SERVER_ERROR, body[:200])
        if status_code == 422:
            return RouteResult(
                True, False, FailureType.VALIDATION_ERROR, body[:200]
            )

        return RouteResult(False, True, None, body[:200])
