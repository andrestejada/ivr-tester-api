"""Unit tests for UpdateIVRArchitectureUseCase."""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.application.exceptions import NotFoundError
from src.application.use_cases.update_ivr_architecture_use_case import (
    UpdateIVRArchitectureUseCase,
)
from src.domain.entities.ivr_architecture import IVRArchitectureEntity


class TestUpdateIVRArchitectureUseCase:
    """Cubre reglas de negocio y contrato del repositorio para update."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self, mock_repository: AsyncMock
    ) -> UpdateIVRArchitectureUseCase:
        return UpdateIVRArchitectureUseCase(repository=mock_repository)

    @pytest.mark.asyncio
    async def test_execute_returns_updated_entity(
        self, use_case: UpdateIVRArchitectureUseCase, mock_repository: AsyncMock
    ) -> None:
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440001")
        user_id = UUID("550e8400-e29b-41d4-a716-446655440002")
        updated_entity = IVRArchitectureEntity(
            id=architecture_id,
            name="Updated IVR",
            phone_number="+12025550100",
            description="Nuevo flujo",
            provider="twilio",
            user_id=user_id,
            created_at=datetime(2025, 1, 1, 10, 0, 0),
        )
        mock_repository.update.return_value = updated_entity

        result = await use_case.execute(
            architecture_id=architecture_id,
            user_id=user_id,
            name="Updated IVR",
            phone_number="+12025550100",
            description="Nuevo flujo",
        )

        assert result == updated_entity
        mock_repository.update.assert_awaited_once_with(
            architecture_id=architecture_id,
            user_id=user_id,
            name="Updated IVR",
            phone_number="+12025550100",
            description="Nuevo flujo",
        )

    @pytest.mark.asyncio
    async def test_execute_raises_not_found_when_repository_returns_none(
        self, use_case: UpdateIVRArchitectureUseCase, mock_repository: AsyncMock
    ) -> None:
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440003")
        user_id = UUID("550e8400-e29b-41d4-a716-446655440004")
        mock_repository.update.return_value = None

        with pytest.raises(NotFoundError, match=f"{architecture_id} not found"):
            await use_case.execute(
                architecture_id=architecture_id,
                user_id=user_id,
                name="Any",
                phone_number="+12025550101",
            )

        mock_repository.update.assert_awaited_once_with(
            architecture_id=architecture_id,
            user_id=user_id,
            name="Any",
            phone_number="+12025550101",
            description=None,
        )

    @pytest.mark.asyncio
    async def test_execute_forwards_description_none_by_default(
        self, use_case: UpdateIVRArchitectureUseCase, mock_repository: AsyncMock
    ) -> None:
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440005")
        user_id = UUID("550e8400-e29b-41d4-a716-446655440006")
        mock_repository.update.return_value = IVRArchitectureEntity(
            id=architecture_id,
            name="IVR sin descripcion",
            phone_number="+12025550102",
            user_id=user_id,
            created_at=datetime(2025, 1, 1, 10, 0, 0),
        )

        await use_case.execute(
            architecture_id=architecture_id,
            user_id=user_id,
            name="IVR sin descripcion",
            phone_number="+12025550102",
        )

        mock_repository.update.assert_awaited_once_with(
            architecture_id=architecture_id,
            user_id=user_id,
            name="IVR sin descripcion",
            phone_number="+12025550102",
            description=None,
        )

    @pytest.mark.asyncio
    async def test_execute_propagates_repository_exceptions(
        self, use_case: UpdateIVRArchitectureUseCase, mock_repository: AsyncMock
    ) -> None:
        architecture_id = UUID("550e8400-e29b-41d4-a716-446655440007")
        user_id = UUID("550e8400-e29b-41d4-a716-446655440008")
        mock_repository.update.side_effect = RuntimeError("db temporarily unavailable")

        with pytest.raises(RuntimeError, match="temporarily unavailable"):
            await use_case.execute(
                architecture_id=architecture_id,
                user_id=user_id,
                name="IVR",
                phone_number="+12025550103",
            )
