"""Integration tests for Test Execution endpoints (list-only)."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import UUID


class TestListTestExecutionsEndpoint:
    """Tests para el endpoint GET /ivr-architectures/{id}/test-cases/{id}/executions."""

    def test_scenario_1_list_successfully(self, test_client, valid_token):
        """Escenario: listar ejecuciones existentes."""
        with patch(
            "src.presentation.dependencies.test_execution_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_gen.return_value = mock_session

            ivr_id = "550e8400-e29b-41d4-a716-446655440000"
            test_case_id = "550e8400-e29b-41d4-a716-446655440010"

            with patch(
                "src.presentation.dependencies.test_execution_dependencies.TestExecutionRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()

                from src.domain.entities.test_execution import TestExecutionEntity
                from datetime import datetime

                mock_repo.list_by_test_case = AsyncMock(
                    return_value=[
                        TestExecutionEntity(
                            id=UUID("550e8400-e29b-41d4-a716-446655440011"),
                            test_case_id=UUID(test_case_id),
                            status="PASSED",
                            duration_seconds=12,
                            provider_call_sid="CA123",
                            executed_at=datetime.now(),
                        ),
                    ]
                )
                mock_repo_class.return_value = mock_repo

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}/executions",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                assert isinstance(response.json(), list)
                if response.json():
                    assert "id" in response.json()[0]
                    assert "status" in response.json()[0]

    def test_scenario_4_get_execution_details_successfully(self, test_client, valid_token):
        """Escenario: obtener detalle de una ejecución con logs & relaciones."""
        with patch(
            "src.presentation.dependencies.test_execution_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_execution_dependencies.TestExecutionRepository"
            ) as mock_repo_class:
                from datetime import datetime
                from types import SimpleNamespace

                ivr_architecture = SimpleNamespace(
                    id="550e8400-e29b-41d4-a716-446655440020",
                    user_id="550e8400-e29b-41d4-a716-446655440030",
                    name="Ventas IVR",
                    phone_number="+1234567890",
                    provider="twilio",
                    description="Test architecture",
                    created_at=datetime(2025, 1, 1),
                )

                test_case = SimpleNamespace(
                    id="550e8400-e29b-41d4-a716-446655440010",
                    ivr_architecture_id=ivr_architecture.id,
                    name="Flujo 1",
                    flow_script=[{"step": 1, "listen": "Hola", "action": "dtmf_1"}],
                    created_at=datetime(2025, 1, 1),
                    ivr_architecture=ivr_architecture,
                )

                execution_model = SimpleNamespace(
                    id="550e8400-e29b-41d4-a716-446655440011",
                    test_case_id=test_case.id,
                    status="PASSED",
                    duration_seconds=12,
                    provider_call_sid="CA123",
                    executed_at=datetime(2025, 1, 2, 12, 0, 0),
                    test_case=test_case,
                    logs=[
                        SimpleNamespace(
                            id="550e8400-e29b-41d4-a716-446655440021",
                            execution_id="550e8400-e29b-41d4-a716-446655440011",
                            step_number=1,
                            expected_text="Hola",
                            actual_transcription="Hola",
                            confidence_score=95.5,
                            action_taken="sent_dtmf_1",
                            created_at=datetime(2025, 1, 2, 12, 0, 1),
                        )
                    ],
                )

                mock_repo = AsyncMock()
                mock_repo.get_by_id_with_details = AsyncMock(return_value=execution_model)
                mock_repo_class.return_value = mock_repo

                ivr_id = "550e8400-e29b-41d4-a716-446655440000"
                test_case_id = "550e8400-e29b-41d4-a716-446655440010"
                execution_id = "550e8400-e29b-41d4-a716-446655440011"

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}/executions/{execution_id}",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                payload = response.json()
                assert payload["id"] == execution_id
                assert payload["test_case"]["id"] == test_case_id
                assert payload["test_case"]["ivr_architecture"]["name"] == "Ventas IVR"
                assert len(payload["logs"]) == 1

    def test_scenario_2_missing_jwt_token(self, test_client):
        """Escenario: debe rechazar sin token."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        test_case_id = "550e8400-e29b-41d4-a716-446655440010"
        response = test_client.get(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}/executions",
        )
        assert response.status_code == 401

    def test_scenario_3_empty_list(self, test_client, valid_token):
        """Escenario: test case sin ejecuciones."""
        with patch(
            "src.presentation.dependencies.test_execution_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_gen.return_value = mock_session

            ivr_id = "550e8400-e29b-41d4-a716-446655440000"
            test_case_id = "550e8400-e29b-41d4-a716-446655440010"

            with patch(
                "src.presentation.dependencies.test_execution_dependencies.TestExecutionRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.list_by_test_case = AsyncMock(return_value=[])
                mock_repo_class.return_value = mock_repo

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/{test_case_id}/executions",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                assert response.json() == []


class TestExecutionAnalyticsEndpoint:
    """Tests para el endpoint GET /ivr-architectures/{id}/test-cases/analytics."""

    def test_scenario_analytics_with_defaults(self, test_client, valid_token):
        """Escenario: obtener analytics con defaults (últimos 7 días, todos los bloques)."""
        from datetime import datetime
        from src.application.dtos import (
            AnalyticsResponse,
            SelectedContext,
            Summary,
            Rankings,
            TrendPoint,
        )

        with patch(
            "src.presentation.dependencies.test_execution_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_execution_dependencies.ExecutionAnalyticsRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()

                # Respuesta mock
                analytics_response = AnalyticsResponse(
                    selected_context=SelectedContext(
                        architecture_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                        architecture_name="Test Arch",
                        test_case_id=None,
                        test_case_name=None,
                        date_from=datetime(2026, 3, 22),
                        date_to=datetime(2026, 3, 29),
                    ),
                    summary=Summary(
                        total_executions=150,
                        passed_count=120,
                        failed_count=25,
                        error_count=5,
                        running_count=0,
                        success_rate=80.0,
                        failure_rate=20.0,
                        avg_duration_seconds=12.5,
                    ),
                    rankings=Rankings(top_failed=[], top_success=[]),
                    trend=[
                        TrendPoint(
                            date="2026-03-22", total=20, passed=16, failed=4, error_count=0
                        ),
                        TrendPoint(
                            date="2026-03-23", total=22, passed=18, failed=4, error_count=0
                        ),
                    ],
                )

                mock_repo.get_execution_analytics = AsyncMock(
                    return_value=analytics_response
                )
                mock_repo_class.return_value = mock_repo

                ivr_id = "550e8400-e29b-41d4-a716-446655440000"

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/analytics",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                payload = response.json()
                assert payload["selected_context"]["architecture_id"] == ivr_id
                assert payload["summary"]["success_rate"] == 80.0
                assert len(payload["trend"]) == 2

    def test_scenario_analytics_summary_only(self, test_client, valid_token):
        """Escenario: obtener solo summary (carga rápida)."""
        from datetime import datetime
        from src.application.dtos import (
            AnalyticsResponse,
            SelectedContext,
            Summary,
        )

        with patch(
            "src.presentation.dependencies.test_execution_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_execution_dependencies.ExecutionAnalyticsRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()

                analytics_response = AnalyticsResponse(
                    selected_context=SelectedContext(
                        architecture_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                        architecture_name="Test Arch",
                        test_case_id=None,
                        test_case_name=None,
                        date_from=datetime(2026, 3, 22),
                        date_to=datetime(2026, 3, 29),
                    ),
                    summary=Summary(
                        total_executions=100,
                        passed_count=85,
                        failed_count=10,
                        error_count=5,
                        running_count=0,
                        success_rate=85.0,
                        failure_rate=10.0,
                        avg_duration_seconds=10.0,
                    ),
                    rankings=None,
                    trend=None,
                )

                mock_repo.get_execution_analytics = AsyncMock(
                    return_value=analytics_response
                )
                mock_repo_class.return_value = mock_repo

                ivr_id = "550e8400-e29b-41d4-a716-446655440000"

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/analytics?include=summary",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                payload = response.json()
                assert payload["summary"] is not None
                assert payload["rankings"] is None
                assert payload["trend"] is None

    def test_scenario_analytics_missing_jwt(self, test_client):
        """Escenario: debe rechazar sin token."""
        ivr_id = "550e8400-e29b-41d4-a716-446655440000"
        response = test_client.get(
            f"/api/v1/ivr-architectures/{ivr_id}/test-cases/analytics",
        )
        assert response.status_code == 401

    def test_scenario_analytics_with_test_case_filter(self, test_client, valid_token):
        """Escenario: filtrar por test case específico."""
        from datetime import datetime
        from src.application.dtos import (
            AnalyticsResponse,
            SelectedContext,
            Summary,
        )

        with patch(
            "src.presentation.dependencies.test_execution_dependencies.get_db_session"
        ) as mock_session_gen:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_gen.return_value = mock_session

            with patch(
                "src.presentation.dependencies.test_execution_dependencies.ExecutionAnalyticsRepository"
            ) as mock_repo_class:
                mock_repo = AsyncMock()

                test_case_id = "550e8400-e29b-41d4-a716-446655440010"
                analytics_response = AnalyticsResponse(
                    selected_context=SelectedContext(
                        architecture_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                        architecture_name="Test Arch",
                        test_case_id=UUID(test_case_id),
                        test_case_name="Login Flow",
                        date_from=datetime(2026, 3, 22),
                        date_to=datetime(2026, 3, 29),
                    ),
                    summary=Summary(
                        total_executions=30,
                        passed_count=24,
                        failed_count=5,
                        error_count=1,
                        running_count=0,
                        success_rate=80.0,
                        failure_rate=20.0,
                        avg_duration_seconds=8.5,
                    ),
                    rankings=None,
                    trend=None,
                )

                mock_repo.get_execution_analytics = AsyncMock(
                    return_value=analytics_response
                )
                mock_repo_class.return_value = mock_repo

                ivr_id = "550e8400-e29b-41d4-a716-446655440000"

                response = test_client.get(
                    f"/api/v1/ivr-architectures/{ivr_id}/test-cases/analytics?test_case_id={test_case_id}&include=summary",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                payload = response.json()
                assert payload["selected_context"]["test_case_id"] == test_case_id
                assert payload["selected_context"]["test_case_name"] == "Login Flow"
