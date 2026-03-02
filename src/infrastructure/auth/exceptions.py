"""Custom exceptions for JWT authentication."""


class TokenError(Exception):
    """Base exception for token validation errors."""

    pass


class InvalidTokenError(TokenError):
    """Raised when token is malformed or signature is invalid."""

    pass


class ExpiredTokenError(TokenError):
    """Raised when token has expired."""

    pass


class MissingTokenError(TokenError):
    """Raised when no token is provided."""

    pass
