"""Tests for custom exceptions."""

from __future__ import annotations

from hippocampus.exceptions import (
    CompilationError,
    GraphError,
    HippocampusError,
    InjectionError,
    RoutingError,
)


class TestExceptionHierarchy:
    """Tests that all exceptions inherit from HippocampusError."""

    def test_routing_error_inherits(self) -> None:
        assert issubclass(RoutingError, HippocampusError)

    def test_graph_error_inherits(self) -> None:
        assert issubclass(GraphError, HippocampusError)

    def test_compilation_error_inherits(self) -> None:
        assert issubclass(CompilationError, HippocampusError)

    def test_injection_error_inherits(self) -> None:
        assert issubclass(InjectionError, HippocampusError)

    def test_base_inherits_from_exception(self) -> None:
        assert issubclass(HippocampusError, Exception)

    def test_can_catch_all_with_base(self) -> None:
        try:
            raise GraphError("test error")
        except HippocampusError as e:
            assert str(e) == "test error"

    def test_each_has_distinct_message(self) -> None:
        errors = [
            RoutingError("routing failed"),
            GraphError("graph failed"),
            CompilationError("compilation failed"),
            InjectionError("injection failed"),
        ]
        messages = [str(e) for e in errors]
        assert len(set(messages)) == len(messages)
