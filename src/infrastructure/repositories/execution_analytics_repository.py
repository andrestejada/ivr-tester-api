"""Infrastructure implementation of Execution Analytics repository using SQLAlchemy."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.dtos import (
    AnalyticsResponse,
    Rankings,
    RankingItem,
    SelectedContext,
    Summary,
    TrendPoint,
)
from src.domain.repositories.execution_analytics_repository import (
    IExecutionAnalyticsRepository,
)
from src.infrastructure.database.models.ivr_architecture import IVRArchitectureModel
from src.infrastructure.database.models.test_case import TestCaseModel
from src.infrastructure.database.models.test_execution import TestExecutionModel, TestStatus

logger = logging.getLogger(__name__)


class ExecutionAnalyticsRepository(IExecutionAnalyticsRepository):
    """SQLAlchemy implementation of Execution Analytics repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_execution_analytics(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        top_n: int = 10,
        include_blocks: list[str] | None = None,
    ) -> AnalyticsResponse:
        """Obtiene analytics agregadas de ejecuciones."""
        if include_blocks is None:
            include_blocks = ["summary", "rankings", "trend"]

        # Obtener contexto (architecture y test case info)
        architecture = await self.session.execute(
            select(IVRArchitectureModel).where(
                IVRArchitectureModel.id == architecture_id
            )
        )
        arch_model = architecture.scalars().first()
        if not arch_model:
            raise ValueError(f"Architecture {architecture_id} not found")

        # Obtener test case info si fue filtrado
        test_case_model = None
        if test_case_id:
            tc_result = await self.session.execute(
                select(TestCaseModel).where(TestCaseModel.id == test_case_id)
            )
            test_case_model = tc_result.scalars().first()

        selected_context = SelectedContext(
            architecture_id=architecture_id,
            architecture_name=arch_model.name,
            test_case_id=test_case_id,
            test_case_name=test_case_model.name if test_case_model else None,
            date_from=date_from,
            date_to=date_to,
        )

        # Obtener bloques solicitados
        summary = None
        rankings = None
        trend = None

        if "summary" in include_blocks:
            summary = await self.get_summary(
                architecture_id, test_case_id, date_from, date_to
            )

        if "rankings" in include_blocks:
            rankings = await self.get_rankings(
                architecture_id, test_case_id, date_from, date_to, top_n
            )

        if "trend" in include_blocks:
            trend = await self.get_trend(
                architecture_id, test_case_id, date_from, date_to
            )

        return AnalyticsResponse(
            selected_context=selected_context,
            summary=summary,
            rankings=rankings,
            trend=trend,
        )

    async def get_summary(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Summary:
        """Obtiene métricas resumidas de ejecuciones."""
        # Construir query base
        query = select(TestExecutionModel).where(
            TestExecutionModel.test_case.has(
                TestCaseModel.ivr_architecture_id == architecture_id
            )
        )

        # Aplicar filtros
        if test_case_id:
            query = query.where(TestExecutionModel.test_case_id == test_case_id)

        if date_from and date_to:
            query = query.where(
                and_(
                    TestExecutionModel.executed_at >= date_from,
                    TestExecutionModel.executed_at <= date_to,
                )
            )

        # Ejecutar query para obtener modelos
        result = await self.session.execute(query)
        executions = result.scalars().all()

        # Calcular métricas
        total = len(executions)
        if total == 0:
            return Summary(
                total_executions=0,
                passed_count=0,
                failed_count=0,
                error_count=0,
                running_count=0,
                success_rate=0.0,
                failure_rate=0.0,
                avg_duration_seconds=None,
            )

        passed = sum(1 for e in executions if e.status == TestStatus.PASSED)
        failed = sum(1 for e in executions if e.status == TestStatus.FAILED)
        error = sum(1 for e in executions if e.status == TestStatus.ERROR)
        running = sum(1 for e in executions if e.status == TestStatus.RUNNING)

        success_rate = (passed / total * 100) if total > 0 else 0.0
        failure_rate = (failed / total * 100) if total > 0 else 0.0

        # Calcular duración promedio (solo de ejecuciones completadas)
        completed = [e for e in executions if e.duration_seconds is not None]
        avg_duration = (
            sum(e.duration_seconds for e in completed) / len(completed)
            if completed
            else None
        )

        return Summary(
            total_executions=total,
            passed_count=passed,
            failed_count=failed,
            error_count=error,
            running_count=running,
            success_rate=round(success_rate, 2),
            failure_rate=round(failure_rate, 2),
            avg_duration_seconds=round(avg_duration, 2) if avg_duration else None,
        )

    async def get_rankings(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        top_n: int = 10,
    ) -> Rankings:
        """Obtiene rankings de test cases por desempeño."""
        # Query: test cases con sus métricas agregadas
        tc_subquery = select(TestCaseModel.id).where(
            TestCaseModel.ivr_architecture_id == architecture_id
        )

        if test_case_id:
            tc_subquery = tc_subquery.where(TestCaseModel.id == test_case_id)

        # Obtener datos agregados por test case
        exec_query = select(TestExecutionModel).where(
            TestExecutionModel.test_case_id.in_(tc_subquery)
        )

        if date_from and date_to:
            exec_query = exec_query.where(
                and_(
                    TestExecutionModel.executed_at >= date_from,
                    TestExecutionModel.executed_at <= date_to,
                )
            )

        result = await self.session.execute(exec_query)
        executions = result.scalars().all()

        # Agrupar por test case
        by_test_case: dict[UUID, list] = {}
        test_case_names: dict[UUID, str] = {}

        for execution in executions:
            tc_id = execution.test_case_id
            if tc_id not in by_test_case:
                by_test_case[tc_id] = []
                # Obtener nombre del test case
                tc_result = await self.session.execute(
                    select(TestCaseModel).where(TestCaseModel.id == tc_id)
                )
                tc_model = tc_result.scalars().first()
                test_case_names[tc_id] = tc_model.name if tc_model else "Unknown"

            by_test_case[tc_id].append(execution)

        # Calcular métricas por test case
        rankings_data = []
        for tc_id, execs in by_test_case.items():
            total = len(execs)
            passed = sum(1 for e in execs if e.status == TestStatus.PASSED)
            failed = sum(1 for e in execs if e.status == TestStatus.FAILED)
            error = sum(1 for e in execs if e.status == TestStatus.ERROR)

            success_rate = (passed / total * 100) if total > 0 else 0.0
            failure_rate = (failed / total * 100) if total > 0 else 0.0

            completed = [e for e in execs if e.duration_seconds is not None]
            avg_duration = (
                sum(e.duration_seconds for e in completed) / len(completed)
                if completed
                else None
            )

            rankings_data.append(
                {
                    "test_case_id": tc_id,
                    "test_case_name": test_case_names.get(tc_id, "Unknown"),
                    "execution_count": total,
                    "passed_count": passed,
                    "failed_count": failed,
                    "error_count": error,
                    "success_rate": round(success_rate, 2),
                    "failure_rate": round(failure_rate, 2),
                    "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None,
                }
            )

        # Top failed (ordenar por failed_count DESC)
        top_failed = sorted(
            rankings_data, key=lambda x: x["failed_count"], reverse=True
        )[:top_n]

        # Top success (ordenar por success_rate DESC)
        top_success = sorted(
            rankings_data, key=lambda x: x["success_rate"], reverse=True
        )[:top_n]

        return Rankings(
            top_failed=[RankingItem(**item) for item in top_failed],
            top_success=[RankingItem(**item) for item in top_success],
        )

    async def get_trend(
        self,
        architecture_id: UUID,
        test_case_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[TrendPoint]:
        """Obtiene serie temporal diaria de ejecuciones."""
        # Query base
        tc_subquery = select(TestCaseModel.id).where(
            TestCaseModel.ivr_architecture_id == architecture_id
        )

        if test_case_id:
            tc_subquery = tc_subquery.where(TestCaseModel.id == test_case_id)

        exec_query = select(TestExecutionModel).where(
            TestExecutionModel.test_case_id.in_(tc_subquery)
        )

        if date_from and date_to:
            exec_query = exec_query.where(
                and_(
                    TestExecutionModel.executed_at >= date_from,
                    TestExecutionModel.executed_at <= date_to,
                )
            )

        result = await self.session.execute(exec_query)
        executions = result.scalars().all()

        # Agrupar por fecha
        by_date: dict[str, list] = {}
        for execution in executions:
            date_str = execution.executed_at.date().isoformat()
            if date_str not in by_date:
                by_date[date_str] = []
            by_date[date_str].append(execution)

        # Crear trend points
        trend_points = []
        for date_str in sorted(by_date.keys()):
            execs = by_date[date_str]
            total = len(execs)
            passed = sum(1 for e in execs if e.status == TestStatus.PASSED)
            failed = sum(1 for e in execs if e.status == TestStatus.FAILED)
            error = sum(1 for e in execs if e.status == TestStatus.ERROR)

            trend_points.append(
                TrendPoint(
                    date=date_str,
                    total=total,
                    passed=passed,
                    failed=failed,
                    error_count=error,
                )
            )

        return trend_points
