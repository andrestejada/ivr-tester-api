"""Use case for retrieving execution analytics."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.dtos import AnalyticsResponse
from src.domain.repositories.execution_analytics_repository import (
    IExecutionAnalyticsRepository,
)


class GetExecutionAnalyticsUseCase:
    """Use case para obtener analytics agregadas de ejecuciones."""

    def __init__(self, repository: IExecutionAnalyticsRepository):
        self.repository = repository

    async def execute(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        top_n: int = 10,
        include_blocks: list[str] | None = None,
    ) -> AnalyticsResponse:
        """Ejecuta el caso de uso de analytics.

        Nota: Los parámetros ya vienen validados por el schema de Pydantic.
        Este use case solo aplica defaults y orquesta al repositorio.

        Args:
            architecture_id: ID de la arquitectura IVR (validado por endpoint)
            test_case_id: Opcional. UUID ya validado por schema.
            date_from: Fecha de inicio. Si es None, defaults a 7 días atrás.
            date_to: Fecha de fin. Si es None, defaults a ahora.
            top_n: Número de items en rankings (validado en schema: 1-50).
            include_blocks: Lista de bloques ya validada ["summary", "rankings", "trend"].

        Returns:
            AnalyticsResponse con bloques solicitados.
        """
        # Apply defaults para fechas
        now = datetime.now(timezone.utc)
        if date_to is None:
            date_to = now
        if date_from is None:
            date_from = now - timedelta(days=7)

        # Usar include_blocks si viene de repositorio, o default
        if include_blocks is None:
            include_blocks = ["summary", "rankings", "trend"]

        # Llamar al repositorio
        response = await self.repository.get_execution_analytics(
            architecture_id=architecture_id,
            test_case_id=test_case_id,
            date_from=date_from,
            date_to=date_to,
            top_n=top_n,
            include_blocks=include_blocks,
        )

        return response
