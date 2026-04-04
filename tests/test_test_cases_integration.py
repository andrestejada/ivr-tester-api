"""Integration tests for Test Case endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import UUID


class TestCreateTestCaseEndpoint:
    """Tests para el endpoint POST /ivr-architectures/{id}/test-cases."""

    def test_scenario_1_create_successfully(self, test_client, valid_token):
        """Escenario 1: Crear caso de prueba exitosamente."""
        with patch(
            "src.presentation.dependencies.test_case_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.flush = AsyncMock()

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_case_dependencies.TestCaseRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.create = AsyncMock(
                    return_value=UUID("550e8400-e29b-41d4-a716-446655440001")
                )
                mock_repo_class.return_value = mock_repo

                ivr_id = "550e8400-e29b-41d4-a716-446655440000"
                response = test_client.post(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
                    json={
                        "name": "Flujo de bienvenida",
                        "flow_script": [
                            {
                                "step": 1,
                                "listen": "Bienvenido al sistema",
                                "action": "send_dtmf_1",
                            },
                        ],
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 201

    def test_scenario_2_missing_jwt_token(self, test_client):
        """Escenario 3: Rechazar sin autenticación JWT."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        response = test_client.post(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
            json={
                "name": "Flujo de bienvenida",
                "flow_script": [
                    {"step": 1, "listen": "Bienvenido", "action": "send_dtmf_1"},
                ],
            },
        )

        assert response.status_code == 401

    def test_scenario_3_name_too_long(self, test_client, valid_token):
        """Escenario 4: Validar nombre máximo 255 caracteres."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        response = test_client.post(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
            json={
                "name": "x" * 256,
                "flow_script": [
                    {"step": 1, "listen": "Bienvenido", "action": "send_dtmf_1"},
                ],
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_4_empty_flow_script(self, test_client, valid_token):
        """Escenario 5: Validar flow_script lista no vacía."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        response = test_client.post(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
            json={
                "name": "Test",
                "flow_script": [],
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_5_invalid_flow_step_structure(self, test_client, valid_token):
        """Escenario 6: Validar estructura de cada paso."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        response = test_client.post(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
            json={
                "name": "Test",
                "flow_script": [
                    {"action": "send_dtmf_1"},  # falta step y listen
                ],
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_6_missing_required_fields(self, test_client, valid_token):
        """Escenario adicional: Validar campos requeridos."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        response = test_client.post(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
            json={
                "name": "Test",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422


class TestListTestCasesEndpoint:
    """Tests para el endpoint GET /ivr-architectures/{id}/test-cases."""

    def test_scenario_1_list_successfully(self, test_client, valid_token):
        """Escenario 2: Listar casos de prueba de una arquitectura."""
        with patch(
            "src.presentation.dependencies.test_case_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_gen.return_value = mock_session

            ivr_id = "550e8400-e29b-41d4-a716-446655440000"

            with patch(
                "src.presentation.dependencies.test_case_dependencies.TestCaseRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()

                # Mock the list_by_architecture method
                from src.domain.entities.test_case import TestCaseEntity
                from datetime import datetime

                mock_repo.list_by_architecture = AsyncMock(
                    return_value=[
                        TestCaseEntity(
                            id=UUID("550e8400-e29b-41d4-a716-446655440001"),
                            ivr_architecture_id=UUID(ivr_id),
                            name="Flujo 1",
                            flow_script=[
                                {"step": 1, "listen": "Bienvenido", "action": "send_dtmf_1"},
                            ],
                            created_at=datetime.now(),
                        ),
                    ]
                )
                mock_repo_class.return_value = mock_repo

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                assert isinstance(response.json(), list)
                if response.json():
                    assert "id" in response.json()[0]
                    assert "name" in response.json()[0]

    def test_scenario_2_missing_jwt_token(self, test_client):
        """Missing JWT token."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        response = test_client.get(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
        )

        assert response.status_code == 401

    def test_scenario_3_empty_list(self, test_client, valid_token):
        """Escenario: Arquitectura sin test cases."""
        with patch(
            "src.presentation.dependencies.test_case_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_gen.return_value = mock_session

            ivr_id = "550e8400-e29b-41d4-a716-446655440000"

            with patch(
                "src.presentation.dependencies.test_case_dependencies.TestCaseRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.list_by_architecture = AsyncMock(return_value=[])
                mock_repo_class.return_value = mock_repo

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                assert response.json() == []


class TestUpdateTestCaseEndpoint:
    """Tests para el endpoint PUT /ivr-architectures/{id}/test-cases/{test_case_id}."""

    def test_scenario_1_update_name_successfully(self, test_client, valid_token):
        """Escenario 1: Actualizar nombre exitosamente."""
        with patch(
            "src.presentation.dependencies.test_case_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.flush = AsyncMock()

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_case_dependencies.TestCaseRepository"
            ) as mock_repo_class:
                from src.domain.entities.test_case import TestCaseEntity
                from datetime import datetime

                mock_repo = AsyncMock()
                ivr_id = "550e8400-e29b-41d4-a716-446655440000"
                test_case_id = "550e8400-e29b-41d4-a716-446655440001"

                # Mock list_by_architecture (para verificar pertenencia)
                mock_repo.list_by_architecture = AsyncMock(
                    return_value=[
                        TestCaseEntity(
                            id=UUID(test_case_id),
                            ivr_architecture_id=UUID(ivr_id),
                            name="Flujo antiguo",
                            flow_script=[{"step": 1, "listen": "Bienvenido"}],
                            created_at=datetime.now(),
                        ),
                    ]
                )
                # Mock update
                mock_repo.update = AsyncMock()
                mock_repo_class.return_value = mock_repo

                response = test_client.put(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}",
                    json={"name": "Nuevo nombre"},
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 204
                mock_repo.update.assert_called_once()

    def test_scenario_2_update_flow_script_successfully(self, test_client, valid_token):
        """Escenario 2: Actualizar flow_script exitosamente."""
        with patch(
            "src.presentation.dependencies.test_case_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.flush = AsyncMock()

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_case_dependencies.TestCaseRepository"
            ) as mock_repo_class:
                from src.domain.entities.test_case import TestCaseEntity
                from datetime import datetime

                mock_repo = AsyncMock()
                ivr_id = "550e8400-e29b-41d4-a716-446655440000"
                test_case_id = "550e8400-e29b-41d4-a716-446655440001"

                mock_repo.list_by_architecture = AsyncMock(
                    return_value=[
                        TestCaseEntity(
                            id=UUID(test_case_id),
                            ivr_architecture_id=UUID(ivr_id),
                            name="Test",
                            flow_script=[{"step": 1, "listen": "Bienvenido"}],
                            created_at=datetime.now(),
                        ),
                    ]
                )
                mock_repo.update = AsyncMock()
                mock_repo_class.return_value = mock_repo

                response = test_client.put(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}",
                    json={
                        "flow_script": [
                            {"step": 1, "listen": "Nuevo flujo"},
                            {"step": 2, "listen": "Paso 2"},
                        ]
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 204
                mock_repo.update.assert_called_once()

    def test_scenario_3_update_both_fields(self, test_client, valid_token):
        """Escenario 3: Actualizar nombre y flow_script."""
        with patch(
            "src.presentation.dependencies.test_case_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.flush = AsyncMock()

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_case_dependencies.TestCaseRepository"
            ) as mock_repo_class:
                from src.domain.entities.test_case import TestCaseEntity
                from datetime import datetime

                mock_repo = AsyncMock()
                ivr_id = "550e8400-e29b-41d4-a716-446655440000"
                test_case_id = "550e8400-e29b-41d4-a716-446655440001"

                mock_repo.list_by_architecture = AsyncMock(
                    return_value=[
                        TestCaseEntity(
                            id=UUID(test_case_id),
                            ivr_architecture_id=UUID(ivr_id),
                            name="Antiguo",
                            flow_script=[{"step": 1, "listen": "Viejo"}],
                            created_at=datetime.now(),
                        ),
                    ]
                )
                mock_repo.update = AsyncMock()
                mock_repo_class.return_value = mock_repo

                response = test_client.put(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}",
                    json={
                        "name": "Nuevo nombre",
                        "flow_script": [{"step": 1, "listen": "Nuevo flujo"}],
                    },
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 204
                mock_repo.update.assert_called_once()

    def test_scenario_4_test_case_not_in_architecture(self, test_client, valid_token):
        """Escenario 4: Test case no pertenece a la arquitectura."""
        with patch(
            "src.presentation.dependencies.test_case_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_case_dependencies.TestCaseRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()
                ivr_id = "550e8400-e29b-41d4-a716-446655440000"
                test_case_id = "550e8400-e29b-41d4-a716-446655440001"

                # Mock retorna lista vacía (test case no existe en esta arquitectura)
                mock_repo.list_by_architecture = AsyncMock(return_value=[])
                mock_repo_class.return_value = mock_repo

                response = test_client.put(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}",
                    json={"name": "Nuevo nombre"},
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 404

    def test_scenario_5_missing_jwt_token(self, test_client):
        """Escenario 5: Rechazar sin autenticación JWT."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        test_case_id = "550e8400-e29b-41d4-a716-446655440001"
        response = test_client.put(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}",
            json={"name": "Nuevo nombre"},
        )

        assert response.status_code == 401

    def test_scenario_6_invalid_name_too_long(self, test_client, valid_token):
        """Escenario 6: Validar nombre máximo 255 caracteres."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        test_case_id = "550e8400-e29b-41d4-a716-446655440001"
        response = test_client.put(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}",
            json={"name": "x" * 256},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422

    def test_scenario_7_invalid_flow_script_empty(self, test_client, valid_token):
        """Escenario 7: Validar flow_script lista no vacía."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        test_case_id = "550e8400-e29b-41d4-a716-446655440001"
        response = test_client.put(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}",
            json={"flow_script": []},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 422
