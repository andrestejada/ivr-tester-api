"""Unit tests for JWT verification module."""

import pytest

from src.infrastructure.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
)
from src.infrastructure.auth.jwt_verifier import verify_supabase_token


class TestVerifySupabaseToken:
    """Tests for verify_supabase_token function."""

    def test_valid_token(self, valid_token):
        """
        Test Scenario 1: Valid token is decoded successfully.

        When: verify_supabase_token called with valid token
        Then: Returns dict with id, email, user_metadata
        """
        result = verify_supabase_token(valid_token)

        assert result["id"] == "test-user-id-123"
        assert result["email"] == "test@example.com"
        assert result["user_metadata"] == {"name": "Test User"}

    def test_expired_token(self, expired_token):
        """
        Test Scenario 3: Expired token raises ExpiredTokenError.

        When: verify_supabase_token called with expired token
        Then: Raises ExpiredTokenError
        """
        with pytest.raises(ExpiredTokenError):
            verify_supabase_token(expired_token)

    def test_malformed_token(self, malformed_token):
        """
        Test: Malformed token raises InvalidTokenError.

        When: verify_supabase_token called with malformed token
        Then: Raises InvalidTokenError
        """
        with pytest.raises(InvalidTokenError):
            verify_supabase_token(malformed_token)

    def test_wrong_signature_token(self, wrong_signature_token):
        """
        Test: Token with wrong signature raises InvalidTokenError.

        When: verify_supabase_token called with wrongly signed token
        Then: Raises InvalidTokenError
        """
        with pytest.raises(InvalidTokenError):
            verify_supabase_token(wrong_signature_token)

    def test_empty_token(self):
        """
        Test: Empty token string raises InvalidTokenError.

        When: verify_supabase_token called with empty string
        Then: Raises InvalidTokenError
        """
        with pytest.raises(InvalidTokenError):
            verify_supabase_token("")
