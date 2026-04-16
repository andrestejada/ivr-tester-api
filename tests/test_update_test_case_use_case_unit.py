"""Unit tests for UpdateTestCaseUseCase."""

from uuid import UUID
from unittest.mock import AsyncMock

import pytest

from src.application.exceptions import NotFoundError
from src.application.use_cases.update_test_case_use_case import UpdateTestCaseUseCase


class TestUpdateTestCaseUseCase:
    """Cubre reglas de negocio y contrato del repositorio para update."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_repository: AsyncMock) -> UpdateTestCaseUseCase:
        return UpdateTestCaseUseCase(repository=mock_repository)

    @pytest.mark.asyncio
    async def test_execute_raises_value_error_when_all_fields_are_none(
        self, use_case: UpdateTestCaseUseCase, mock_repository: AsyncMock
    ) -> None:
        test_case_id = UUID("550e8400-e29b-41d4-a716-446655440010")

        with pytest.raises(ValueError, match="At least one field"):
            await use_case.execute(test_case_id=test_case_id)

        mock_repository.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_updates_name_only(
        self, use_case: UpdateTestCaseUseCase, mock_repository: AsyncMock
    ) -> None:
        test_case_id = UUID("550e8400-e29b-41d4-a716-446655440011")

        await use_case.execute(test_case_id=test_case_id, name="Nuevo nombre")

        mock_repository.update.assert_awaited_once_with(
            test_case_id=test_case_id,
            name="Nuevo nombre",
            flow_script=None,
        )

    @pytest.mark.asyncio
    async def test_execute_updates_flow_script_only(
        self, use_case: UpdateTestCaseUseCase, mock_repository: AsyncMock
    ) -> None:
        test_case_id = UUID("550e8400-e29b-41d4-a716-446655440012")
        flow_script = [
            {"step": 1, "listen": "Bienvenido", "action": "send_dtmf_1"},
            {"step": 2, "listen": "Para ventas marque 2"},
        ]

        await use_case.execute(test_case_id=test_case_id, flow_script=flow_script)

        mock_repository.update.assert_awaited_once_with(
            test_case_id=test_case_id,
            name=None,
            flow_script=flow_script,
        )

    @pytest.mark.asyncio
    async def test_execute_updates_name_and_flow_script(
        self, use_case: UpdateTestCaseUseCase, mock_repository: AsyncMock
    ) -> None:
        test_case_id = UUID("550e8400-e29b-41d4-a716-446655440013")
        flow_script = [{"step": 1, "listen": "Hola"}]

        await use_case.execute(
            test_case_id=test_case_id,
            name="Flujo actualizado",
            flow_script=flow_script,
        )

        mock_repository.update.assert_awaited_once_with(
            test_case_id=test_case_id,
            name="Flujo actualizado",
            flow_script=flow_script,
        )

    @pytest.mark.asyncio
    async def test_execute_propagates_not_found_error_from_repository(
        self, use_case: UpdateTestCaseUseCase, mock_repository: AsyncMock
    ) -> None:
        test_case_id = UUID("550e8400-e29b-41d4-a716-446655440014")
        mock_repository.update.side_effect = NotFoundError("Test case not found")

        with pytest.raises(NotFoundError, match="Test case not found"):
            await use_case.execute(test_case_id=test_case_id, name="Nuevo")

        mock_repository.update.assert_awaited_once()
