"""Dependency injection for Test Execution use cases."""

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.application.use_cases import (
    ListTestExecutionsUseCase,
    GetTestExecutionDetailsUseCase,
    GetExecutionAnalyticsUseCase,
)
from src.infrastructure.repositories import (
    TestExecutionRepository,
    ExecutionAnalyticsRepository,
)
from src.infrastructure.database.session import get_db_session


async def get_list_test_executions_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> ListTestExecutionsUseCase:
    """Dependency para inyectar ListTestExecutionsUseCase."""
    repository = TestExecutionRepository(session)
    return ListTestExecutionsUseCase(repository)


async def get_test_execution_details_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> GetTestExecutionDetailsUseCase:
    """Dependency para inyectar GetTestExecutionDetailsUseCase."""
    repository = TestExecutionRepository(session)
    return GetTestExecutionDetailsUseCase(repository)


async def get_execution_analytics_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> GetExecutionAnalyticsUseCase:
    """Dependency para inyectar GetExecutionAnalyticsUseCase."""
    repository = ExecutionAnalyticsRepository(session)
    return GetExecutionAnalyticsUseCase(repository)
