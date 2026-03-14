"""Repository interface for Execution Log domain entity."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.execution_log import ExecutionLogEntity


class IExecutionLogRepository(ABC):
    """Interfaz para el repositorio de logs de ejecución de steps."""

    @abstractmethod
    async def create(self, log: ExecutionLogEntity) -> ExecutionLogEntity:
        """Crea un nuevo log de step en la BD.
        
        Args:
            log: Entidad ExecutionLogEntity a persistir
            
        Returns:
            La entidad creada con id generado
        """
        pass

    @abstractmethod
    async def list_by_execution(self, execution_id: UUID) -> list[ExecutionLogEntity]:
        """Lista todos los logs de una ejecución.
        
        Args:
            execution_id: ID de la ejecución padre
            
        Returns:
            Lista de ExecutionLogEntity ordenada por step_number
        """
        pass
