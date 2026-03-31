"""Repository interface for Execution Analytics domain."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.application.dtos import (
    AnalyticsResponse,
    SelectedContext,
    Summary,
    Rankings,
    TrendPoint,
)


class IExecutionAnalyticsRepository(ABC):
    """Interfaz para el repositorio de analytics de ejecuciones."""

    @abstractmethod
    async def get_execution_analytics(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        top_n: int = 10,
        include_blocks: list[str] | None = None,
    ) -> AnalyticsResponse:
        """Obtiene analytics agregadas de ejecuciones.

        Args:
            architecture_id: ID de la arquitectura IVR
            test_case_id: Opcional. Si se proporciona, filtra por test case específico.
            date_from: Fecha de inicio (inclusive). Si es None, se usa 7 días atrás.
            date_to: Fecha de fin (inclusive). Si es None, se usa ahora.
            top_n: Número de items en el ranking (1-50). Default: 10.
            include_blocks: Lista de bloques a incluir: ["summary", "rankings", "trend"].
                           Si es None, incluye todos.

        Returns:
            AnalyticsResponse con:
            - selected_context: contexto de filtros aplicados
            - summary: métricas resumidas (si en include_blocks)
            - rankings: top test cases por fallos/éxitos (si en include_blocks)
            - trend: serie temporal diaria (si en include_blocks)

        Raises:
            ValueError: Si el rango de fechas es inválido o > 90 días.
            NotFoundError: Si la arquitectura no existe.
        """
        pass

    @abstractmethod
    async def get_summary(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Summary:
        """Obtiene métricas resumidas de ejecuciones.

        Returns:
            Summary con total, conteos y tasas.
        """
        pass

    @abstractmethod
    async def get_rankings(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        top_n: int = 10,
    ) -> Rankings:
        """Obtiene rankings de test cases por desempeño.

        Returns:
            Rankings con top_failed y top_success.
        """
        pass

    @abstractmethod
    async def get_trend(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[TrendPoint]:
        """Obtiene serie temporal diaria de ejecuciones.

        Returns:
            Lista de TrendPoint ordenados por fecha ascendente.
        """
        pass
