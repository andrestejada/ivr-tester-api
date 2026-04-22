import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID

from src.application.exceptions import NotFoundError
from src.presentation.dependencies import get_delete_ivr_architecture_use_case


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
                "phone_number": "555-ABC-4567",
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


class TestUpdateIVRArchitectureEndpoint:
    def test_scenario_1_update_successfully(self, test_client, valid_token):
        """Test actualización exitosa de IVR Architecture."""
        from datetime import datetime
        from src.domain.entities.ivr_architecture import IVRArchitectureEntity
        
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        user_id = UUID("660f9411-f40c-42e5-b827-557766551111")
        
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
                # Mock entity actualizada
                updated_entity = IVRArchitectureEntity(
                    id=architecture_id,
                    name="Updated Sales IVR",
                    phone_number="+12025551234",
                    user_id=user_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    provider="twilio",
                    description="Updated description",
                )
                
                mock_repo = AsyncMock()
                mock_repo.update = AsyncMock(return_value=updated_entity)
                mock_repo_class.return_value = mock_repo

                response = test_client.put(
                    f"/api/v1/ivr-architectures/{architecture_id}",
                    json={
                        "name": "Updated Sales IVR",
                        "phone_number": "+12025551234",
                        "description": "Updated description",
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                assert response.json()["name"] == "Updated Sales IVR"
                assert response.json()["phone_number"] == "+12025551234"

    def test_scenario_2_update_name_exceeds_max_length(self, test_client, valid_token):
        """Test validación de nombre en actualización."""
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        
        response = test_client.put(
            f"/api/v1/ivr-architectures/{architecture_id}",
            json={
                "name": "x" * 251,
                "phone_number": "5551234567",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_3_update_phone_with_invalid_chars(self, test_client, valid_token):
        """Test validación de teléfono en actualización."""
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        
        response = test_client.put(
            f"/api/v1/ivr-architectures/{architecture_id}",
            json={
                "name": "Sales IVR",
                "phone_number": "555-ABC-4567",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_4_update_not_found(self, test_client, valid_token):
        """Test actualización de IVR inexistente."""
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        
        with patch(
            "src.presentation.dependencies.ivr_architecture_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.ivr_architecture_dependencies.IVRArchitectureRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.update = AsyncMock(return_value=None)
                mock_repo_class.return_value = mock_repo

                response = test_client.put(
                    f"/api/v1/ivr-architectures/{architecture_id}",
                    json={
                        "name": "Updated IVR",
                        "phone_number": "5551234567",
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 404

    def test_scenario_5_update_missing_jwt(self, test_client):
        """Test actualización sin autenticación."""
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        
        response = test_client.put(
            f"/api/v1/ivr-architectures/{architecture_id}",
            json={
                "name": "Updated IVR",
                "phone_number": "5551234567",
            },
        )

        assert response.status_code == 401

    def test_scenario_6_update_description_optional(self, test_client, valid_token):
        """Test actualización sin descripción."""
        from datetime import datetime
        from src.domain.entities.ivr_architecture import IVRArchitectureEntity
        
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        user_id = UUID("660f9411-f40c-42e5-b827-557766551111")
        
        with patch(
            "src.presentation.dependencies.ivr_architecture_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.ivr_architecture_dependencies.IVRArchitectureRepository"
            ) as mock_repo_class:
                updated_entity = IVRArchitectureEntity(
                    id=architecture_id,
                    name="Updated IVR",
                    phone_number="+12025551234",
                    user_id=user_id,
                    created_at=datetime.now(),
                    provider="twilio",
                    description=None,
                )
                
                mock_repo = AsyncMock()
                mock_repo.update = AsyncMock(return_value=updated_entity)
                mock_repo_class.return_value = mock_repo

                response = test_client.put(
                    f"/api/v1/ivr-architectures/{architecture_id}",
                    json={
                        "name": "Updated IVR",
                        "phone_number": "+12025551234",
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                assert response.json()["description"] is None


class TestDeleteIVRArchitectureEndpoint:
    def test_scenario_1_delete_successfully(self, test_client, valid_token):
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=None)

        test_client.app.dependency_overrides[get_delete_ivr_architecture_use_case] = (
            lambda: mock_use_case
        )
        try:
            architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
            response = test_client.delete(
                f"/api/v1/ivr-architectures/{architecture_id}",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

            assert response.status_code == 204
            mock_use_case.execute.assert_called_once()
        finally:
            test_client.app.dependency_overrides.pop(
                get_delete_ivr_architecture_use_case,
                None,
            )

    def test_scenario_2_delete_not_found(self, test_client, valid_token):
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(side_effect=NotFoundError("not found"))

        test_client.app.dependency_overrides[get_delete_ivr_architecture_use_case] = (
            lambda: mock_use_case
        )
        try:
            architecture_id = UUID("550e8400-e29b-41d4-a716-446655440000")
            response = test_client.delete(
                f"/api/v1/ivr-architectures/{architecture_id}",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "IVR Architecture not found"
        finally:
            test_client.app.dependency_overrides.pop(
                get_delete_ivr_architecture_use_case,
                None,
            )
