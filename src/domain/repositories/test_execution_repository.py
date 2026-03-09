"""Repository interface for Test Execution domain entity."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.test_execution import TestExecutionEntity


class ITestExecutionRepository(ABC):
    """Interfaz para el repositorio de ejecuciones de casos de prueba."""

    @abstractmethod
    async def list_by_test_case(
        self, test_case_id: UUID
    ) -> list[TestExecutionEntity]:
        """Lista todas las ejecuciones de un Test Case."""
        pass

    @abstractmethod
    async def get_by_id(self, execution_id: UUID) -> TestExecutionEntity:
        """Obtiene una ejecución por ID."""
        pass
