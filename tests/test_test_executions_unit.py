"""Unit tests for Test Execution DTOs and use case."""

from datetime import datetime
from uuid import UUID

import pytest

from src.application.dtos import TestExecutionResponse
from src.application.use_cases.list_test_executions_use_case import ListTestExecutionsUseCase
from src.domain.entities.test_execution import TestExecutionEntity


class TestExecutionResponseSchema:
    """Verifica que el DTO acepte atributos y serialice correctamente."""

    def test_response_from_entity(self):
        now = datetime.now()
        entity = TestExecutionEntity(
            id=UUID("550e8400-e29b-41d4-a716-446655440011"),
            test_case_id=UUID("550e8400-e29b-41d4-a716-446655440010"),
            status="PASSED",
            duration_seconds=5,
            provider_call_sid="CA123",
            executed_at=now,
        )
        dto = TestExecutionResponse.from_orm(entity)
        assert dto.id == entity.id
        assert dto.status == "PASSED"
        assert dto.duration_seconds == 5
        assert dto.executed_at == now


class TestListTestExecutionsUseCase:
    """Asegura que el use case mapea correctamente las entidades a DTOs."""

    @pytest.mark.asyncio
    async def test_execute_returns_dtos(self):
        # fake repository with AsyncMock
        class FakeRepo:
            async def list_by_test_case(self, test_case_id):
                return [
                    TestExecutionEntity(
                        id=UUID("550e8400-e29b-41d4-a716-446655440011"),
                        test_case_id=test_case_id,
                        status="FAILED",
                        duration_seconds=None,
                        provider_call_sid=None,
                        executed_at=datetime(2025, 1, 1),
                    )
                ]

        use_case = ListTestExecutionsUseCase(FakeRepo())
        result = await use_case.execute(UUID("550e8400-e29b-41d4-a716-446655440010"))
        assert isinstance(result, list)
        assert result[0].status == "FAILED"


class TestGetTestExecutionDetailsUseCase:
    """Asegura que el use case de detalle mapea el modelo ORM a DTO."""

    @pytest.mark.asyncio
    async def test_execute_returns_detailed_dto(self):
        from datetime import datetime
        from types import SimpleNamespace

        ivr_architecture = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440020"),
            user_id=UUID("550e8400-e29b-41d4-a716-446655440030"),
            name="Ventas IVR",
            phone_number="+1234567890",
            provider="twilio",
            description="Test architecture",
            created_at=datetime(2025, 1, 1),
        )

        test_case = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440010"),
            ivr_architecture_id=ivr_architecture.id,
            name="Flujo 1",
            flow_script=[{"step": 1, "listen": "Hola", "action": "dtmf_1"}],
            created_at=datetime(2025, 1, 1),
            ivr_architecture=ivr_architecture,
        )

        execution_model = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440011"),
            test_case_id=test_case.id,
            status="PASSED",
            duration_seconds=12,
            provider_call_sid="CA123",
            full_call_transcript="Hola\nMundo\n",
            executed_at=datetime(2025, 1, 2, 12, 0, 0),
            test_case=test_case,
            logs=[
                SimpleNamespace(
                    id=UUID("550e8400-e29b-41d4-a716-446655440021"),
                    execution_id=UUID("550e8400-e29b-41d4-a716-446655440011"),
                    step_number=1,
                    expected_text="Hola",
                    actual_transcription="Hola",
                    confidence_score=95.5,
                    action_taken="sent_dtmf_1",
                    created_at=datetime(2025, 1, 2, 12, 0, 1),
                )
            ],
        )

        class FakeDetailsRepo:
            async def get_by_id_with_details(self, execution_id):
                return execution_model

        from src.application.use_cases.get_test_execution_details_use_case import GetTestExecutionDetailsUseCase

        use_case = GetTestExecutionDetailsUseCase(FakeDetailsRepo())
        result = await use_case.execute(execution_id=execution_model.id)

        assert result.id == execution_model.id
        assert result.status == "PASSED"
        assert result.full_call_transcript == "Hola\nMundo\n"
        assert result.test_case.id == test_case.id
        assert result.test_case.ivr_architecture.name == "Ventas IVR"
        assert len(result.logs) == 1


class TestGetExecutionAnalyticsUseCase:
    """Tests para el caso de uso de analytics de ejecuciones."""

    @pytest.mark.asyncio
    async def test_execute_applies_defaults(self):
        """Verifica que aplica defaults de fecha (últimos 7 días)."""
        from datetime import datetime, timedelta, timezone
        from src.application.use_cases.get_execution_analytics_use_case import (
            GetExecutionAnalyticsUseCase,
        )
        from src.application.dtos import (
            AnalyticsResponse,
            SelectedContext,
            Summary,
            Rankings,
        )

        class FakeAnalyticsRepo:
            async def get_execution_analytics(
                self,
                architecture_id,
                test_case_id=None,
                date_from=None,
                date_to=None,
                top_n=10,
                include_blocks=None,
            ):
                # Verificar que se aplicaron defaults
                assert date_from is not None
                assert date_to is not None
                assert (date_to - date_from).days == 7

                return AnalyticsResponse(
                    selected_context=SelectedContext(
                        architecture_id=architecture_id,
                        architecture_name="Test Arch",
                        test_case_id=test_case_id,
                        test_case_name=None,
                        date_from=date_from,
                        date_to=date_to,
                    ),
                    summary=Summary(
                        total_executions=10,
                        passed_count=8,
                        failed_count=2,
                        error_count=0,
                        running_count=0,
                        success_rate=80.0,
                        failure_rate=20.0,
                        avg_duration_seconds=5.5,
                    ),
                    rankings=Rankings(),
                    trend=[],
                )

        use_case = GetExecutionAnalyticsUseCase(FakeAnalyticsRepo())
        result = await use_case.execute(
            architecture_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            include_blocks=["summary"],
        )

        assert result.selected_context.architecture_id == UUID(
            "550e8400-e29b-41d4-a716-446655440000"
        )
        assert result.summary is not None
        assert result.summary.success_rate == 80.0

    @pytest.mark.asyncio
    async def test_execute_validates_date_range(self):
        """Verifica que valida rango máximo de 90 días."""
        from datetime import datetime, timedelta, timezone
        from src.application.use_cases.get_execution_analytics_use_case import
 GetExecutionAnalyticsUseCase

        class FakeAnalyticsRepo:
            async def get_execution_analytics(self, **kwargs):
                pass

        use_case = GetExecutionAnalyticsUseCase(FakeAnalyticsRepo())

        # Rango > 90 días debe fallar
        now = datetime.now(timezone.utc)
        too_far = now - timedelta(days=91)

        with pytest.raises(ValueError, match="Date range cannot exceed 90 days"):
            await use_case.execute(
                architecture_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                date_from=too_far,
                date_to=now,
            )

    @pytest.mark.asyncio
    async def test_execute_validates_top_n(self):
        """Verifica que valida top_n entre 1 y 50."""
        from src.application.use_cases.get_execution_analytics_use_case import (
            GetExecutionAnalyticsUseCase,
        )

        class FakeAnalyticsRepo:
            async def get_execution_analytics(self, **kwargs):
                pass

        use_case = GetExecutionAnalyticsUseCase(FakeAnalyticsRepo())

        # top_n fuera de rango debe fallar
        with pytest.raises(ValueError, match="top_n must be between 1 and 50"):
            await use_case.execute(
                architecture_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                top_n=51,
            )

