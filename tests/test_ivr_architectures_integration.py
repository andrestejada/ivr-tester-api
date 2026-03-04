import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID


class TestCreateIVRArchitectureEndpoint:
    def test_scenario_1_create_successfully(self, test_client, valid_token):
        with patch(
            "src.presentation.dependencies.ivr_architecture_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock()

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.ivr_architecture_dependencies.IVRArchitectureRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=UUID("550e8400-e29b-41d4-a716-446655440000"))
                mock_repo_class.return_value = mock_repo

                response = test_client.post(
                    "/api/v1/ivr-architectures",
                    json={
                        "name": "Sales IVR",
                        "phone_number": "5551234567",
                        "description": "Sistema IVR para ventas",
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 201

    def test_scenario_2_name_exceeds_max_length(self, test_client, valid_token):
        response = test_client.post(
            "/api/v1/ivr-architectures",
            json={
                "name": "x" * 251,
                "phone_number": "5551234567",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_3_phone_with_special_chars(self, test_client, valid_token):
        response = test_client.post(
            "/api/v1/ivr-architectures",
            json={
                "name": "Sales IVR",
                "phone_number": "555-123-4567",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_4_missing_jwt_token(self, test_client):
        response = test_client.post(
            "/api/v1/ivr-architectures",
            json={
                "name": "Sales IVR",
                "phone_number": "5551234567",
            },
        )

        assert response.status_code == 401

    def test_scenario_5_missing_required_fields(self, test_client, valid_token):
        response = test_client.post(
            "/api/v1/ivr-architectures",
            json={
                "name": "Sales IVR",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_6_description_optional(self, test_client, valid_token):
        with patch(
            "src.presentation.dependencies.ivr_architecture_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock()

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.ivr_architecture_dependencies.IVRArchitectureRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(return_value=UUID("550e8400-e29b-41d4-a716-446655440000"))
                mock_repo_class.return_value = mock_repo

                response = test_client.post(
                    "/api/v1/ivr-architectures",
                    json={
                        "name": "Sales IVR",
                        "phone_number": "5551234567",
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 201
