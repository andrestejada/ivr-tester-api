"""DTOs for Execution Analytics responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SelectedContext(BaseModel):
    """Contexto de filtros aplicados en la consulta."""

    architecture_id: UUID | None = None
    architecture_name: str | None = None
    test_case_id: UUID | None = None
    test_case_name: str | None = None
    date_from: datetime
    date_to: datetime

    model_config = {"from_attributes": True}


class Summary(BaseModel):
    """Métricas resumidas de ejecuciones."""

    total_executions: int
    passed_count: int
    failed_count: int
    error_count: int
    running_count: int = 0
    success_rate: float = Field(
        description="Porcentaje de ejecuciones exitosas (0-100)", ge=0, le=100
    )
    failure_rate: float = Field(
        description="Porcentaje de ejecuciones fallidas (0-100)", ge=0, le=100
    )
    avg_duration_seconds: float | None = Field(
        default=None, description="Duración promedio en segundos"
    )

    model_config = {"from_attributes": True}


class RankingItem(BaseModel):
    """Item individual en el ranking de test cases."""

    test_case_id: UUID
    test_case_name: str
    execution_count: int
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    success_rate: float | None = Field(
        default=None, description="Tasa de éxito (0-100)"
    )
    failure_rate: float | None = Field(
        default=None, description="Tasa de fallo (0-100)"
    )
    avg_duration_seconds: float | None = Field(
        default=None, description="Duración promedio en segundos"
    )

    model_config = {"from_attributes": True}


class Rankings(BaseModel):
    """Rankings de test cases por desempeño."""

    top_failed: list[RankingItem] = Field(
        default_factory=list, description="Top N test cases con más fallos"
    )
    top_success: list[RankingItem] = Field(
        default_factory=list, description="Top N test cases con más éxitos"
    )

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    """Punto de serie temporal diaria (agregación diaria)."""

    date: str = Field(description="Fecha en formato YYYY-MM-DD")
    total: int = Field(description="Total de ejecuciones en el día")
    passed: int = Field(description="Ejecuciones exitosas")
    failed: int = Field(description="Ejecuciones fallidas")
    error_count: int = Field(default=0, description="Ejecuciones con error")

    model_config = {"from_attributes": True}


class AnalyticsResponse(BaseModel):
    """Respuesta agregada de analytics para dashboard."""

    selected_context: SelectedContext
    summary: Summary | None = None
    rankings: Rankings | None = None
    trend: list[TrendPoint] | None = None

    model_config = {"from_attributes": True}
