"""API Router for Analytics endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.infrastructure.auth.dependencies import get_current_user
from src.application.use_cases import GetExecutionAnalyticsUseCase
from src.application.dtos import AnalyticsResponse
from src.presentation.api.v1.schemas.analytics import ExecutionAnalyticsQuery
from src.presentation.dependencies import get_execution_analytics_use_case


router = APIRouter(prefix="/ivr-architectures", tags=["analytics"])


@router.get(
    "/{ivr_architecture_id}/test-cases/analytics",
    response_model=AnalyticsResponse,
)
async def get_execution_analytics(
    ivr_architecture_id: UUID,
    _: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[
        GetExecutionAnalyticsUseCase, Depends(get_execution_analytics_use_case)
    ],
    test_case_id: UUID | None = Query(
        default=None,
        description="Optional test case UUID to filter analytics by.",
    ),
    date_from: datetime | None = Query(
        default=None,
        description="Start date (ISO8601). Defaults to 7 days ago.",
    ),
    date_to: datetime | None = Query(
        default=None,
        description="End date (ISO8601). Defaults to now.",
    ),
    top_n: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Number of items in rankings (1-50).",
    ),
    include: str = Query(
        default="summary,rankings,trend",
        description="Comma-separated list of blocks: 'summary', 'rankings', 'trend'. "
                    "Example: 'summary,trend' returns only summary and trend.",
    ),
):
    """Obtiene métricas agregadas de ejecuciones de test cases.
    
    Permite exploración de datos con filtros opcionales y bloques seleccionables
    para construir dashboards dinámicos.
    
    Args:
        ivr_architecture_id: ID de la arquitectura IVR (ruta)
        test_case_id: Opcional. Filtrar por test case específico.
        date_from: Opcional. Start date (ISO8601). Defaults: 7 días atrás.
        date_to: Opcional. End date (ISO8601). Defaults: now.
        top_n: Número de items en rankings (1-50). Default: 10.
        include: Comma-separated blocks ('summary', 'rankings', 'trend').
                 Default: todas.
    
    Returns:
        AnalyticsResponse con contexto + bloques solicitados:
        - selected_context: Filtros aplicados
        - summary: Métricas resumidas (si incluido)
        - rankings: Top test cases (si incluido)
        - trend: Serie temporal diaria (si incluido)
    
    Examples:
        - `/analytics` → Retorna todo (all blocks)
        - `/analytics?include=summary` → Solo métricas resumidas (rápido)
        - `/analytics?include=rankings,trend&top_n=5` → Top 5 + tendencia
        - `/analytics?test_case_id=<uuid>&date_from=2026-03-22` → Filtros custom
    """
    # Validar y parsear query params usando schema
    query = ExecutionAnalyticsQuery(
        test_case_id=test_case_id,
        date_from=date_from,
        date_to=date_to,
        top_n=top_n,
        include=include.split(",") if include else ["summary", "rankings", "trend"],
    )

    # Ejecutar use case
    analytics = await use_case.execute(
        architecture_id=ivr_architecture_id,
        test_case_id=query.test_case_id,
        date_from=query.date_from,
        date_to=query.date_to,
        top_n=query.top_n,
        include_blocks=query.include,
    )

    return analytics
