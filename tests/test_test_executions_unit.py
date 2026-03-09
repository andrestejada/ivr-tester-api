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
