"""Infrastructure implementation of IExecutionLogRepository."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.domain.entities.execution_log import ExecutionLogEntity
from src.domain.repositories.execution_log_repository import IExecutionLogRepository
from src.infrastructure.database.models.execution_log import ExecutionLogModel

logger = logging.getLogger(__name__)


class ExecutionLogRepository(IExecutionLogRepository):
    """Implementación de repositorio de Execution Log contra BD."""

    def __init__(self, session: AsyncSession) -> None:
        """Inicializa con sesión SQLAlchemy.
        
        Args:
            session: AsyncSession de SQLAlchemy
        """
        self.session = session

    async def create(self, log: ExecutionLogEntity) -> ExecutionLogEntity:
        """Crea un nuevo log de step en la BD.
        
        Args:
            log: Entidad ExecutionLogEntity a persistir
            
        Returns:
            La entidad creada con id generado
        """
        log_id = log.id or uuid4()
        
        model = ExecutionLogModel(
            id=log_id,
            execution_id=log.execution_id,
            step_number=log.step_number,
            expected_text=log.expected_text,
            actual_transcription=log.actual_transcription,
            confidence_score=log.confidence_score,
            action_taken=log.action_taken,
        )
        
        self.session.add(model)
        await self.session.flush()
        
        logger.debug(
            f"Created execution log: exec_id={log.execution_id}, "
            f"step={log.step_number}"
        )
        
        return self._to_entity(model)

    async def list_by_execution(self, execution_id: UUID) -> list[ExecutionLogEntity]:
        """Lista todos los logs de una ejecución.
        
        Args:
            execution_id: ID de la ejecución padre
            
        Returns:
            Lista de ExecutionLogEntity ordenada por step_number
        """
        result = await self.session.execute(
            select(ExecutionLogModel)
            .where(ExecutionLogModel.execution_id == execution_id)
            .order_by(ExecutionLogModel.step_number.asc())
        )
        
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    @staticmethod
    def _to_entity(model: ExecutionLogModel) -> ExecutionLogEntity:
        """Convierte modelo a entidad."""
        return ExecutionLogEntity(
            id=model.id,
            execution_id=model.execution_id,
            step_number=model.step_number,
            expected_text=model.expected_text,
            actual_transcription=model.actual_transcription,
            confidence_score=model.confidence_score,
            action_taken=model.action_taken,
            created_at=model.created_at,
        )
