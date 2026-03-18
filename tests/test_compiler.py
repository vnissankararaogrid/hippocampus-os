"""Tests for the State Guard compiler."""

from __future__ import annotations

from hippocampus.compiler import StateGuard, StateGuardCompiler


class TestStateGuard:
    """Tests for the StateGuard dataclass and XML rendering."""

    def test_to_xml_renders_correctly(self) -> None:
        guard = StateGuard(
            action="salesforce_query",
            error_type="auth_expired",
            detail="403 Forbidden",
            severity="critical",
            directive="Do NOT retry. Pivot to refresh auth.",
        )
        xml = guard.to_xml()
        assert '<STATE_GUARD priority="critical">' in xml
        assert "ACTION_FAILED: salesforce_query" in xml
        assert "ERROR: auth_expired" in xml
        assert "DIRECTIVE: Do NOT retry" in xml
        assert "</STATE_GUARD>" in xml


class TestStateGuardCompiler:
    """Tests for StateGuardCompiler."""

    def setup_method(self) -> None:
        self.compiler = StateGuardCompiler(max_guards=3)

    def test_compile_empty_list_returns_empty_string(self) -> None:
        result = self.compiler.compile([])
        assert result == ""

    def test_compile_single_failure(self) -> None:
        failures = [
            {
                "action": "salesforce_query",
                "error_type": "auth_expired",
                "detail": "403 Forbidden - Authentication expired",
                "relevance": 0.95,
            }
        ]
        result = self.compiler.compile(failures)
        assert "<CONTEXT_ENGINEERING>" in result
        assert "</CONTEXT_ENGINEERING>" in result
        assert '<STATE_GUARD priority="critical">' in result
        assert "auth_expired" in result
        assert "credentials need to be refreshed" in result

    def test_compile_multiple_failures(self) -> None:
        failures = [
            {
                "action": "api_call",
                "error_type": "auth_expired",
                "detail": "Token expired",
                "relevance": 0.9,
            },
            {
                "action": "another_call",
                "error_type": "rate_limited",
                "detail": "Too many requests",
                "relevance": 0.7,
            },
        ]
        result = self.compiler.compile(failures)
        assert result.count("<STATE_GUARD") == 2

    def test_compile_respects_max_guards(self) -> None:
        compiler = StateGuardCompiler(max_guards=2)
        failures = [
            {
                "action": f"action_{i}",
                "error_type": "server_error",
                "detail": f"Error {i}",
                "relevance": 0.8,
            }
            for i in range(5)
        ]
        result = compiler.compile(failures)
        assert result.count("<STATE_GUARD") == 2

    def test_compile_unknown_error_type_uses_default_directive(self) -> None:
        failures = [
            {
                "action": "test_action",
                "error_type": "unknown_error_type",
                "detail": "Something went wrong",
                "relevance": 0.6,
            }
        ]
        result = self.compiler.compile(failures)
        assert "Do NOT retry this action. It previously failed." in result

    def test_compile_single_method(self) -> None:
        failure = {
            "action": "db_query",
            "error_type": "permission_denied",
            "detail": "Access denied",
            "relevance": 0.85,
        }
        result = self.compiler.compile_single(failure)
        assert "<CONTEXT_ENGINEERING>" in result
        assert "permission_denied" in result

    def test_detail_truncated_to_150_chars(self) -> None:
        failures = [
            {
                "action": "test",
                "error_type": "server_error",
                "detail": "x" * 500,
                "relevance": 0.9,
            }
        ]
        result = self.compiler.compile(failures)
        # The detail in the XML should be limited
        assert "ERROR: server_error" in result

    def test_auth_expired_is_critical_severity(self) -> None:
        failures = [
            {
                "action": "test",
                "error_type": "auth_expired",
                "detail": "Token expired",
                "relevance": 0.9,
            }
        ]
        result = self.compiler.compile(failures)
        assert 'priority="critical"' in result

    def test_server_error_is_high_severity(self) -> None:
        failures = [
            {
                "action": "test",
                "error_type": "server_error",
                "detail": "500 error",
                "relevance": 0.9,
            }
        ]
        result = self.compiler.compile(failures)
        assert 'priority="high"' in result

    def test_apology_loop_is_high_severity(self) -> None:
        failures = [
            {
                "action": "test",
                "error_type": "apology_loop",
                "detail": "Looping",
                "relevance": 0.9,
            }
        ]
        result = self.compiler.compile(failures)
        assert 'priority="high"' in result
