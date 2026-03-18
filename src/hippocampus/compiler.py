"""State Guard compiler — transforms failures into XML directives."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import CompilationError


@dataclass
class StateGuard:
    """A compiled directive injected into the system prompt.

    Attributes:
        action: The action that failed.
        error_type: The classified error type.
        detail: Error detail text (max 150 chars).
        severity: "critical", "high", or "medium".
        directive: The pivot instruction for the LLM.
    """

    action: str
    error_type: str
    detail: str
    severity: str
    directive: str

    def to_xml(self) -> str:
        """Render this guard as XML for injection into system prompt."""
        return (
            f'<STATE_GUARD priority="{self.severity}">\n'
            f"ACTION_FAILED: {self.action}\n"
            f"ERROR: {self.error_type} — {self.detail}\n"
            f"DIRECTIVE: {self.directive}\n"
            f"</STATE_GUARD>"
        )


# Mapping from failure type to directive text
DIRECTIVE_MAP: dict[str, str] = {
    "auth_expired": (
        "Do NOT retry this action. Authentication has expired. "
        "Pivot: Inform the user that credentials need to be "
        "refreshed and ask for updated authentication."
    ),
    "rate_limited": (
        "Do NOT retry this action immediately. You are being "
        "rate-limited. Pivot: Inform the user of the rate limit "
        "and suggest waiting before retrying."
    ),
    "not_found": (
        "Do NOT retry this action with the same parameters. "
        "The resource does not exist. Pivot: Inform the user "
        "the resource was not found and ask for clarification."
    ),
    "server_error": (
        "Do NOT retry this action. The external service is "
        "experiencing an error. Pivot: Inform the user of the "
        "service issue and suggest trying later."
    ),
    "permission_denied": (
        "Do NOT retry this action. You lack permission. "
        "Pivot: Inform the user that access is denied and "
        "suggest checking permissions."
    ),
    "apology_loop": (
        "You are in an apology loop. STOP apologizing. "
        "Pivot: Acknowledge the failure ONCE, then propose "
        "a concrete alternative action or ask the user for guidance."
    ),
    "validation_error": (
        "Do NOT retry with the same input. The input was invalid. "
        "Pivot: Ask the user for corrected input with specific "
        "validation requirements."
    ),
}

DEFAULT_DIRECTIVE = (
    "Do NOT retry this action. It previously failed. "
    "Pivot to an alternative approach."
)


class StateGuardCompiler:
    """Compiles episodic failures into un-ignorable context guards.

    Transforms raw failure data into structured XML directives that
    get injected at position 0 of the system prompt for maximum
    LLM attention.
    """

    def __init__(self, max_guards: int = 3) -> None:
        """Initialize compiler.

        Args:
            max_guards: Maximum number of guards per compilation.
        """
        self.max_guards = max_guards

    def compile(self, failures: list[dict]) -> str:
        """Compile multiple failures into a single guard block.

        Args:
            failures: List of failure dicts from EpisodicGraph.

        Returns:
            XML string wrapped in <CONTEXT_ENGINEERING> tags.
            Empty string if no failures provided.

        Raises:
            CompilationError: If compilation fails.
        """
        if not failures:
            return ""

        try:
            guards: list[str] = []
            for f in failures[: self.max_guards]:
                error_type = f.get("error_type", "unknown")
                directive = DIRECTIVE_MAP.get(error_type, DEFAULT_DIRECTIVE)

                severity = (
                    "critical"
                    if error_type in ("auth_expired", "permission_denied")
                    else "high"
                )

                guard = StateGuard(
                    action=f.get("action", "unknown_action"),
                    error_type=error_type,
                    detail=f.get("detail", "")[:150],
                    severity=severity,
                    directive=directive,
                )
                guards.append(guard.to_xml())

            combined = "\n".join(guards)
            return f"<CONTEXT_ENGINEERING>\n{combined}\n</CONTEXT_ENGINEERING>"

        except Exception as exc:
            raise CompilationError(f"Failed to compile guards: {exc}") from exc

    def compile_single(self, failure: dict) -> str:
        """Compile a single failure into a guard.

        Args:
            failure: A single failure dict.

        Returns:
            XML string for the single failure.
        """
        return self.compile([failure])
