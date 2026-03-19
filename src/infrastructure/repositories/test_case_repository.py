"""Infrastructure implementation of Test Case repository using SQLAlchemy."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.application.exceptions import NotFoundError
from src.domain.repositories.test_case_repository import ITestCaseRepository
from src.domain.entities.test_case import TestCaseEntity
from src.infrastructure.database.models.test_case import TestCaseModel


class TestCaseRepository(ITestCaseRepository):
    """SQLAlchemy implementation of Test Case repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        ivr_architecture_id: UUID,
        name: str,
        flow_script: list[dict],
    ) -> UUID:
        """Crea un nuevo Test Case en la base de datos."""
        model = TestCaseModel(
            ivr_architecture_id=ivr_architecture_id,
            name=name,
            flow_script=flow_script,
        )
        self.session.add(model)
        await self.session.flush()
        return model.id

    async def list_by_architecture(
        self, ivr_architecture_id: UUID
    ) -> list[TestCaseEntity]:
        """Lista todos los Test Cases de una arquitectura."""
        result = await self.session.execute(
            select(TestCaseModel)
            .where(TestCaseModel.ivr_architecture_id == ivr_architecture_id)
            .order_by(TestCaseModel.created_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_by_id(self, test_case_id: UUID) -> TestCaseEntity:
        """Obtiene un Test Case por ID."""
        result = await self.session.execute(
            select(TestCaseModel).where(TestCaseModel.id == test_case_id)
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundError(f"Test Case {test_case_id} not found")
        return self._to_entity(model)

    async def delete(self, test_case_id: UUID) -> None:
        """Elimina un Test Case."""
        model = await self.session.get(TestCaseModel, test_case_id)
        if not model:
            raise NotFoundError(f"Test Case {test_case_id} not found")
        await self.session.delete(model)

    @staticmethod
    def _to_entity(model: TestCaseModel) -> TestCaseEntity:
        """Convierte un TestCaseModel a TestCaseEntity."""
        return TestCaseEntity(
            id=model.id,
            ivr_architecture_id=model.ivr_architecture_id,
            name=model.name,
            flow_script=model.flow_script,
            created_at=model.created_at,
        )
