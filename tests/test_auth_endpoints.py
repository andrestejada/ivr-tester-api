"""Integration tests for authentication endpoints."""

import pytest


class TestGetCurrentUserEndpoint:
    """Tests for GET /api/v1/me endpoint."""

    def test_get_me_with_valid_token(self, test_client, valid_token):
        """
        Test Scenario 1: Request with valid token returns user data.

        Given: Authenticated user
        When: GET /api/v1/me with valid token in Authorization header
        Then: Returns 200 with user id, email, user_metadata
        """
        response = test_client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-user-id-123"
        assert data["email"] == "test@example.com"
        assert data["user_metadata"] == {"name": "Test User"}

    def test_get_me_without_token(self, test_client):
        """
        Test Scenario 2: Request without token returns 401.

        Given: Unauthenticated request
        When: GET /api/v1/me without Authorization header
        Then: Returns 401 with message "Token de autenticación requerido"
        """
        response = test_client.get("/api/v1/me")

        assert response.status_code == 401
        data = response.json()
        assert "Token de autenticación requerido" in data["detail"]

    def test_get_me_with_expired_token(self, test_client, expired_token):
        """
        Test Scenario 3: Request with expired token returns 401.

        Given: User provides expired token
        When: GET /api/v1/me with expired token in Authorization header
        Then: Returns 401 with message "Token inválido o expirado"
        """
        response = test_client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "Token inválido o expirado" in data["detail"]

    def test_get_me_with_malformed_token(self, test_client, malformed_token):
        """
        Test: Request with malformed token returns 401.

        Given: User provides malformed token
        When: GET /api/v1/me with malformed token in Authorization header
        Then: Returns 401 with message "Token inválido o expirado"
        """
        response = test_client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {malformed_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "Token inválido o expirado" in data["detail"]

    def test_get_me_with_wrong_signature(self, test_client, wrong_signature_token):
        """
        Test: Request with wrong signature token returns 401.

        Given: User provides token with wrong signature
        When: GET /api/v1/me with wrongly signed token
        Then: Returns 401 with message "Token inválido o expirado"
        """
        response = test_client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {wrong_signature_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "Token inválido o expirado" in data["detail"]


class TestHealthEndpoint:
    """Tests for GET /api/v1/health endpoint."""

    def test_health_check_public(self, test_client):
        """
        Test: Health endpoint is PUBLIC (no authentication required).

        Given: Any client
        When: GET /api/v1/health without Authorization header
        Then: Returns 200 with status "ok"
        """
        response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_check_with_token(self, test_client, valid_token):
        """
        Test: Health endpoint works even with token (still public).

        Given: Any client with valid token
        When: GET /api/v1/health with Authorization header
        Then: Returns 200 with status "ok"
        """
        response = test_client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
