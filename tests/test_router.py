"""Tests for the deterministic state router."""

from __future__ import annotations

from hippocampus.router import FailureType, RouteResult, StateRouter


class TestStateRouterTextRouting:
    """Tests for StateRouter.route() — text content classification."""

    def setup_method(self) -> None:
        self.router = StateRouter()

    # --- Auth Expired ---

    def test_auth_expired_403_forbidden(self) -> None:
        result = self.router.route("403 Forbidden - Authentication required")
        assert result.is_failure is True
        assert result.error_type == FailureType.AUTH_EXPIRED

    def test_auth_expired_token_invalid(self) -> None:
        result = self.router.route("The token is invalid or has expired")
        assert result.is_failure is True
        assert result.error_type == FailureType.AUTH_EXPIRED

    def test_auth_expired_credentials(self) -> None:
        result = self.router.route("Your credentials have expired")
        assert result.is_failure is True
        assert result.error_type == FailureType.AUTH_EXPIRED

    # --- Rate Limited ---

    def test_rate_limited_429(self) -> None:
        result = self.router.route("429 Too Many Requests - rate limit exceeded")
        assert result.is_failure is True
        assert result.error_type == FailureType.RATE_LIMITED

    def test_rate_limited_text(self) -> None:
        result = self.router.route("Rate limit hit, please slow down")
        assert result.is_failure is True
        assert result.error_type == FailureType.RATE_LIMITED

    # --- Not Found ---

    def test_not_found_404(self) -> None:
        result = self.router.route("404 Not Found - resource does not exist")
        assert result.is_failure is True
        assert result.error_type == FailureType.NOT_FOUND

    # --- Server Error ---

    def test_server_error_500(self) -> None:
        result = self.router.route("500 Internal Server Error")
        assert result.is_failure is True
        assert result.error_type == FailureType.SERVER_ERROR

    def test_server_error_502(self) -> None:
        result = self.router.route("502 Server Error - bad gateway")
        assert result.is_failure is True
        assert result.error_type == FailureType.SERVER_ERROR

    # --- Apology Loop ---

    def test_apology_loop_double_sorry(self) -> None:
        result = self.router.route(
            "I'm sorry, I apologize for the inconvenience. Let me try again. "
            "Let me try again with a different approach."
        )
        assert result.is_failure is True
        assert result.error_type == FailureType.APOLOGY_LOOP

    # --- Permission Denied ---

    def test_permission_denied_403(self) -> None:
        result = self.router.route("403 Forbidden - access denied")
        assert result.is_failure is True
        assert result.error_type == FailureType.PERMISSION_DENIED

    # --- Validation Error ---

    def test_validation_error_422(self) -> None:
        result = self.router.route("422 Validation Error - invalid input")
        assert result.is_failure is True
        assert result.error_type == FailureType.VALIDATION_ERROR

    # --- Success cases ---

    def test_normal_response_is_success(self) -> None:
        result = self.router.route(
            "Here is the data you requested: {'revenue': 50000}"
        )
        assert result.is_success is True
        assert result.is_failure is False
        assert result.error_type is None

    def test_empty_response_is_success(self) -> None:
        result = self.router.route("")
        assert result.is_success is True

    def test_helpful_response_is_success(self) -> None:
        result = self.router.route(
            "I've successfully retrieved the report. Here it is."
        )
        assert result.is_success is True


class TestStateRouterStatusCodeRouting:
    """Tests for StateRouter.route_tool_result() — HTTP status code routing."""

    def setup_method(self) -> None:
        self.router = StateRouter()

    def test_401_is_auth_expired(self) -> None:
        result = self.router.route_tool_result(401, "Unauthorized")
        assert result.error_type == FailureType.AUTH_EXPIRED

    def test_403_is_auth_expired(self) -> None:
        result = self.router.route_tool_result(403, "Forbidden")
        assert result.error_type == FailureType.AUTH_EXPIRED

    def test_429_is_rate_limited(self) -> None:
        result = self.router.route_tool_result(429, "Too many requests")
        assert result.error_type == FailureType.RATE_LIMITED

    def test_404_is_not_found(self) -> None:
        result = self.router.route_tool_result(404, "Not found")
        assert result.error_type == FailureType.NOT_FOUND

    def test_500_is_server_error(self) -> None:
        result = self.router.route_tool_result(500, "Internal server error")
        assert result.error_type == FailureType.SERVER_ERROR

    def test_503_is_server_error(self) -> None:
        result = self.router.route_tool_result(503, "Service unavailable")
        assert result.error_type == FailureType.SERVER_ERROR

    def test_422_is_validation_error(self) -> None:
        result = self.router.route_tool_result(422, "Unprocessable entity")
        assert result.error_type == FailureType.VALIDATION_ERROR

    def test_200_is_success(self) -> None:
        result = self.router.route_tool_result(200, '{"status": "ok"}')
        assert result.is_success is True
        assert result.is_failure is False

    def test_201_is_success(self) -> None:
        result = self.router.route_tool_result(201, "Created")
        assert result.is_success is True


class TestRouteResultSeverity:
    """Tests for RouteResult.severity property."""

    def test_auth_expired_is_critical(self) -> None:
        result = RouteResult(
            is_failure=True,
            is_success=False,
            error_type=FailureType.AUTH_EXPIRED,
            detail="test",
        )
        assert result.severity == "critical"

    def test_permission_denied_is_critical(self) -> None:
        result = RouteResult(
            is_failure=True,
            is_success=False,
            error_type=FailureType.PERMISSION_DENIED,
            detail="test",
        )
        assert result.severity == "critical"

    def test_rate_limited_is_high(self) -> None:
        result = RouteResult(
            is_failure=True,
            is_success=False,
            error_type=FailureType.RATE_LIMITED,
            detail="test",
        )
        assert result.severity == "high"

    def test_apology_loop_is_medium(self) -> None:
        result = RouteResult(
            is_failure=True,
            is_success=False,
            error_type=FailureType.APOLOGY_LOOP,
            detail="test",
        )
        assert result.severity == "medium"
