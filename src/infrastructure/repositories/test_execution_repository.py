"""Infrastructure implementation of Test Execution repository using SQLAlchemy."""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.application.exceptions import NotFoundError
from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.domain.entities.test_execution import TestExecutionEntity
from src.infrastructure.database.models.test_execution import TestExecutionModel, TestStatus
from src.infrastructure.database.models.test_case import TestCaseModel
from src.infrastructure.database.models.execution_log import ExecutionLogModel

logger = logging.getLogger(__name__)


class TestExecutionRepository(ITestExecutionRepository):
    """SQLAlchemy implementation of Test Execution repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, test_case_id: UUID, status: str, provider_call_sid: str | None = None
    ) -> TestExecutionEntity:
        """Crea una nueva ejecución.
        
        Args:
            test_case_id: ID del test case
            status: Estado inicial
            provider_call_sid: ID de llamada del proveedor
            
        Returns:
            TestExecutionEntity creada
        """
        execution_id = uuid4()
        
        model = TestExecutionModel(
            id=execution_id,
            test_case_id=test_case_id,
            status=TestStatus(status),
            provider_call_sid=provider_call_sid,
        )
        
        self.session.add(model)
        await self.session.flush()
        
        logger.info(f"Created test execution: {execution_id}")
        return self._to_entity(model)

    async def list_by_test_case(
        self, test_case_id: UUID
    ) -> list[TestExecutionEntity]:
        """Lista todas las ejecuciones asociadas a un Test Case."""
        result = await self.session.execute(
            select(TestExecutionModel)
            .where(TestExecutionModel.test_case_id == test_case_id)
            .order_by(TestExecutionModel.executed_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_by_id(self, execution_id: UUID) -> TestExecutionEntity:
        """Obtiene una ejecución por su ID."""
        result = await self.session.execute(
            select(TestExecutionModel).where(TestExecutionModel.id == execution_id)
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundError(f"Test execution {execution_id} not found")
        return self._to_entity(model)

    async def get_by_id_with_details(self, execution_id: UUID) -> TestExecutionModel:
        """Obtiene una ejecución por su ID con sus relaciones precargadas para análisis forense.
        
        Realiza eager loading de:
        - test_case con su relación ivr_architecture
        - logs ordenados por step_number
        
        Args:
            execution_id: ID de la ejecución
            
        Returns:
            TestExecutionModel con relaciones precargadas (test_case, ivr_architecture, logs)
            
        Raises:
            NotFoundError: Si no existe la ejecución
        """
        result = await self.session.execute(
            select(TestExecutionModel)
            .where(TestExecutionModel.id == execution_id)
            .options(
                selectinload(TestExecutionModel.test_case).selectinload(
                    TestCaseModel.ivr_architecture
                ),
                selectinload(TestExecutionModel.logs),
            )
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundError(f"Test execution {execution_id} not found")
        
        logger.info(f"Retrieved execution details: {execution_id}")
        return model

    async def update_status(
        self, execution_id: UUID, status: str, duration_seconds: int | None = None
    ) -> TestExecutionEntity:
        """Actualiza el estado de una ejecución.
        
        Args:
            execution_id: ID de la ejecución
            status: Nuevo estado
            duration_seconds: Duración total
            
        Returns:
            TestExecutionEntity actualizada
        """
        result = await self.session.execute(
            select(TestExecutionModel).where(TestExecutionModel.id == execution_id)
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundError(f"Test execution {execution_id} not found")
        
        model.status = TestStatus(status)
        if duration_seconds is not None:
            model.duration_seconds = duration_seconds
        
        await self.session.flush()
        logger.info(f"Updated execution {execution_id}: status={status}")
        
        return self._to_entity(model)

    async def update_full_call_transcript(
        self, execution_id: UUID, full_call_transcript: str
    ) -> TestExecutionEntity:
        """Actualiza la transcripción completa de la llamada.
        
        Args:
            execution_id: ID de la ejecución
            full_call_transcript: Texto completo de la llamada
            
        Returns:
            TestExecutionEntity actualizada
        """
        result = await self.session.execute(
            select(TestExecutionModel).where(TestExecutionModel.id == execution_id)
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundError(f"Test execution {execution_id} not found")
        
        model.full_call_transcript = full_call_transcript
        await self.session.flush()
        logger.info(f"Updated execution {execution_id}: transcript length={len(full_call_transcript or '')} chars")
        
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: TestExecutionModel) -> TestExecutionEntity:
        """Convierte un TestExecutionModel en TestExecutionEntity."""
        return TestExecutionEntity(
            id=model.id,
            test_case_id=model.test_case_id,
            status=model.status.value if hasattr(model.status, "value") else model.status,
            duration_seconds=model.duration_seconds,
            provider_call_sid=model.provider_call_sid,
            executed_at=model.executed_at,
            full_call_transcript=model.full_call_transcript,
        )
