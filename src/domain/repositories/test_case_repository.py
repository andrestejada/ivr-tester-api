"""Repository interface for Test Case domain entity."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.test_case import TestCaseEntity


class ITestCaseRepository(ABC):
    """Interfaz para el repositorio de Test Case."""

    @abstractmethod
    async def create(
        self,
        ivr_architecture_id: UUID,
        name: str,
        flow_script: list[dict],
    ) -> UUID:
        """Crea un nuevo Test Case."""
        pass

    @abstractmethod
    async def list_by_architecture(
        self, ivr_architecture_id: UUID
    ) -> list[TestCaseEntity]:
        """Lista todos los Test Cases de una arquitectura IVR."""
        pass

    @abstractmethod
    async def get_by_id(self, test_case_id: UUID) -> TestCaseEntity:
        """Obtiene un Test Case por ID."""
        pass

    @abstractmethod
    async def delete(self, test_case_id: UUID) -> None:
        """Elimina un Test Case."""
        pass
