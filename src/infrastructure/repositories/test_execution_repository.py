"""Infrastructure implementation of Test Execution repository using SQLAlchemy."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.domain.entities.test_execution import TestExecutionEntity
from src.infrastructure.database.models.test_execution import TestExecutionModel


class TestExecutionRepository(ITestExecutionRepository):
    """SQLAlchemy implementation of Test Execution repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

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
            raise ValueError(f"Test execution {execution_id} not found")
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
        )
