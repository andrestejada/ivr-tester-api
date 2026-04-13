"""Unit tests for application error utilities."""

import pytest
from src.application.utils.error_utils import (
    sanitize_error_message,
    classify_error_category,
    get_user_friendly_error_message,
)


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message function."""

    def test_sanitize_removes_ansi_codes(self):
        """Verifica que remueve códigos ANSI color."""
        error_with_ansi = "\x1b[31mRed error\x1b[0m"
        result = sanitize_error_message(error_with_ansi)
        assert result == "Red error"
        assert "\x1b" not in result

    def test_sanitize_removes_ansi_alternative_format(self):
        """Verifica que remueve códigos ANSI en formato alternativo."""
        error_with_ansi = "\033[32mGreen success\033[0m"
        result = sanitize_error_message(error_with_ansi)
        assert result == "Green success"
        assert "\033" not in result

    def test_sanitize_replaces_newlines_with_pipe(self):
        """Verifica que reemplaza newlines con | para legibilidad."""
        error_multiline = "Line 1\nLine 2\nLine 3"
        result = sanitize_error_message(error_multiline)
        assert result == "Line 1 | Line 2 | Line 3"
        assert "\n" not in result

    def test_sanitize_replaces_tabs_with_spaces(self):
        """Verifica que reemplaza tabs con espacios."""
        error_with_tab = "Column1\tColumn2\tColumn3"
        result = sanitize_error_message(error_with_tab)
        assert result == "Column1 Column2 Column3"
        assert "\t" not in result

    def test_sanitize_removes_multiple_spaces(self):
        """Verifica que consolida múltiples espacios en uno."""
        error_with_spaces = "Multiple    spaces    here"
        result = sanitize_error_message(error_with_spaces)
        assert result == "Multiple spaces here"

    def test_sanitize_truncates_long_messages(self):
        """Verifica que trunca mensajes largos a max_length."""
        long_error = "x" * 300
        result = sanitize_error_message(long_error, max_length=255)
        assert len(result) <= 255
        assert result.endswith("...")
        assert len(result) == 255

    def test_sanitize_respects_custom_max_length(self):
        """Verifica que respeta max_length personalizado."""
        long_error = "a" * 100
        result = sanitize_error_message(long_error, max_length=50)
        assert len(result) <= 50
        assert result.endswith("...")

    def test_sanitize_short_message_not_truncated(self):
        """Verifica que no trunca si está bajo max_length."""
        short_error = "Short error"
        result = sanitize_error_message(short_error, max_length=255)
        assert result == "Short error"
        assert not result.endswith("...")

    def test_sanitize_strips_leading_trailing_spaces(self):
        """Verifica que remueve espacios al inicio/final."""
        error_with_spaces = "   Error message   "
        result = sanitize_error_message(error_with_spaces)
        assert result == "Error message"
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_sanitize_handles_exception_object(self):
        """Verifica que funciona con objetos Exception."""
        exc = ValueError("Invalid value")
        result = sanitize_error_message(exc)
        assert "Invalid value" in result


class TestClassifyErrorCategory:
    """Tests for classify_error_category function."""

    # Network errors
    def test_classify_dns_resolution_error(self):
        """Verifica clasificación de errores DNS."""
        dns_errors = [
            "nameresolution error",
            "getaddrinfo failed",
            "dns resolution timeout",
            "failed to resolve api.example.com",
        ]
        for error in dns_errors:
            assert classify_error_category(error) == "network"

    def test_classify_connection_error(self):
        """Verifica clasificación de errores de conexión."""
        conn_errors = [
            "connection refused",
            "connection reset by peer",
            "network unreachable",
            "connectionerror timeout",
        ]
        for error in conn_errors:
            assert classify_error_category(error) == "network"

    def test_classify_socket_error(self):
        """Verifica clasificación de errores socket."""
        socket_errors = [
            "socket error 11001",
            "errno 111 connection refused",
        ]
        for error in socket_errors:
            assert classify_error_category(error) == "network"

    # Timeout errors
    def test_classify_timeout_error(self):
        """Verifica clasificación de errores timeout."""
        timeout_errors = [
            "read timed out",
            "write timeout",
            "deadline exceeded",
            "operation timed out",
        ]
        for error in timeout_errors:
            assert classify_error_category(error) == "timeout"

    # Auth errors
    def test_classify_auth_error(self):
        """Verifica clasificación de errores de autenticación."""
        auth_errors = [
            "unauthorized access",
            "authentication failed",
            "invalid credentials provided",
            "invalid token signature",
            "permission denied",
            "forbidden",
            "401 unauthorized",
            "403 forbidden",
        ]
        for error in auth_errors:
            assert classify_error_category(error) == "auth"

    # Service unavailable
    def test_classify_unavailable_error(self):
        """Verifica clasificación de errores de servicio unavailable."""
        unavailable_errors = [
            "service unavailable",
            "internal server error",
            "500 error",
            "502 bad gateway",
            "503 service unavailable",
            "504 gateway timeout",
        ]
        for error in unavailable_errors:
            assert classify_error_category(error) == "unavailable"

    # Invalid input
    def test_classify_invalid_input_error(self):
        """Verifica clasificación de errores de entrada inválida."""
        invalid_errors = [
            "invalid parameter",
            "bad request",
            "validation error",
            "400 bad request",
            "malformed json",
        ]
        for error in invalid_errors:
            assert classify_error_category(error) == "invalid_input"

    # Unknown
    def test_classify_unknown_error(self):
        """Verifica clasificación de errores desconocidos."""
        unknown_errors = [
            "something weird happened",
            "mysterious error",
            "unknown failure",
        ]
        for error in unknown_errors:
            assert classify_error_category(error) == "unknown"

    def test_classify_case_insensitive(self):
        """Verifica que la clasificación no es sensible a mayúsculas."""
        assert classify_error_category("UNAUTHORIZED ACCESS") == "auth"
        assert classify_error_category("Connection Refused") == "network"
        assert classify_error_category("SERVICE UNAVAILABLE") == "unavailable"

    def test_classify_with_exception_object(self):
        """Verifica que funciona con objetos Exception."""
        exc = TimeoutError("Deadline exceeded")
        assert classify_error_category(exc) == "timeout"


class TestGetUserFriendlyErrorMessage:
    """Tests for get_user_friendly_error_message function."""

    def test_network_friendly_message(self):
        """Verifica mensaje amigable para errores de red."""
        msg = get_user_friendly_error_message(
            "Connection refused",
            error_category="network"
        )
        assert "connection" in msg.lower()
        assert "network" in msg.lower()
        assert len(msg) < 255

    def test_auth_friendly_message(self):
        """Verifica mensaje amigable para errores de autenticación."""
        msg = get_user_friendly_error_message(
            "Invalid credentials",
            error_category="auth"
        )
        assert "authentication" in msg.lower()
        assert "credentials" in msg.lower()
        assert len(msg) < 255

    def test_timeout_friendly_message(self):
        """Verifica mensaje amigable para timeouts."""
        msg = get_user_friendly_error_message(
            "Request timed out",
            error_category="timeout"
        )
        assert "timeout" in msg.lower() or "long" in msg.lower()
        assert len(msg) < 255

    def test_unavailable_friendly_message(self):
        """Verifica mensaje amigable para servicio unavailable."""
        msg = get_user_friendly_error_message(
            "Service unavailable",
            error_category="unavailable"
        )
        assert "unavailable" in msg.lower() or "temporarily" in msg.lower()
        assert len(msg) < 255

    def test_invalid_input_friendly_message(self):
        """Verifica mensaje amigable para entrada inválida."""
        msg = get_user_friendly_error_message(
            "Invalid parameter value",
            error_category="invalid_input"
        )
        assert "invalid" in msg.lower() or "configuration" in msg.lower()
        assert len(msg) < 255

    def test_unknown_friendly_message(self):
        """Verifica mensaje amigable para errores desconocidos."""
        msg = get_user_friendly_error_message(
            "Unknown weird error",
            error_category="unknown"
        )
        assert "unexpected" in msg.lower() or "error" in msg.lower()
        assert len(msg) < 255

    def test_auto_classify_when_not_provided(self):
        """Verifica que clasifica automáticamente si no se proporciona categoría."""
        msg = get_user_friendly_error_message("Connection refused")
        assert msg is not None
        assert len(msg) > 0
        assert "connection" in msg.lower() or "network" in msg.lower()

    def test_hides_technical_details(self):
        """Verifica que oculta detalles técnicos."""
        technical_error = (
            "HTTPSConnectionPool(host='api.example.com'): "
            "Max retries exceeded"
        )
        msg = get_user_friendly_error_message(technical_error)
        assert "api.example.com" not in msg
        assert "HTTPSConnectionPool" not in msg
        assert "Max retries" not in msg

    def test_all_messages_are_safe_for_ui(self):
        """Verifica que todos los mensajes son seguros para UI."""
        categories = [
            "network",
            "auth",
            "timeout",
            "unavailable",
            "invalid_input",
            "unknown",
        ]
        for category in categories:
            msg = get_user_friendly_error_message(
                "Some error",
                error_category=category
            )
            assert len(msg) < 255
            assert "\n" not in msg
            assert "\t" not in msg
            assert "<" not in msg
            assert ">" not in msg
