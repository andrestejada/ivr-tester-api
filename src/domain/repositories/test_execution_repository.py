"""Repository interface for Test Execution domain entity."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.test_execution import TestExecutionEntity


class ITestExecutionRepository(ABC):
    """Interfaz para el repositorio de ejecuciones de casos de prueba."""

    @abstractmethod
    async def create(
        self, test_case_id: UUID, status: str, provider_call_sid: str | None = None
    ) -> TestExecutionEntity:
        """Crea una nueva ejecución de test case.
        
        Args:
            test_case_id: ID del test case a ejecutar
            status: Estado inicial (ej: "RUNNING", "PASSED", "FAILED", "ERROR")
            provider_call_sid: ID de llamada asignado por proveedor (ej: Twilio CallSid)
            
        Returns:
            TestExecutionEntity con id generado y executed_at seteado
        """
        pass

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

    @abstractmethod
    async def update_status(
        self, execution_id: UUID, status: str, duration_seconds: int | None = None
    ) -> TestExecutionEntity:
        """Actualiza el estado de una ejecución.
        
        Args:
            execution_id: ID de la ejecución
            status: Nuevo estado (PASSED, FAILED, ERROR)
            duration_seconds: Duración total de la ejecución en segundos
            
        Returns:
            TestExecutionEntity actualizada
        """
        pass

    @abstractmethod
    async def update_full_call_transcript(
        self, execution_id: UUID, full_call_transcript: str
    ) -> TestExecutionEntity:
        """Actualiza la transcripción completa de la llamada.
        
        Args:
            execution_id: ID de la ejecución
            full_call_transcript: Texto completo de la llamada para debugging
            
        Returns:
            TestExecutionEntity actualizada
        """
        pass
