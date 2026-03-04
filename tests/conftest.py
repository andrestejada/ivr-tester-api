"""Pytest configuration and shared fixtures for tests."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from src.infrastructure.config import settings
from src.presentation.app import create_app


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    app = create_app()
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for making requests to the API."""
    return TestClient(test_app)


@pytest.fixture
def valid_token():
    """Create a valid JWT token for testing."""
    test_user_id = str(uuid4())
    payload = {
        "sub": test_user_id,
        "email": "test@example.com",
        "user_metadata": {"name": "Test User"},
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return token


@pytest.fixture
def expired_token():
    """Create an expired JWT token for testing."""
    test_user_id = str(uuid4())
    payload = {
        "sub": test_user_id,
        "email": "test@example.com",
        "user_metadata": {"name": "Test User"},
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    token = jwt.encode(
        payload,
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return token


@pytest.fixture
def malformed_token():
    """Create a malformed JWT token for testing."""
    return "not-a-valid-jwt-token-at-all"


@pytest.fixture
def wrong_signature_token():
    """Create a JWT token with wrong signature for testing."""
    test_user_id = str(uuid4())
    payload = {
        "sub": test_user_id,
        "email": "test@example.com",
        "user_metadata": {"name": "Test User"},
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        "wrong-secret-key",
        algorithm="HS256",
    )
    return token
