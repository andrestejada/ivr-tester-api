"""Dependency injection for Test Case use cases."""

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.application.use_cases import CreateTestCaseUseCase, ListTestCasesUseCase
from src.infrastructure.repositories import TestCaseRepository
from src.infrastructure.database.session import get_db_session


async def get_create_test_case_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> CreateTestCaseUseCase:
    """Dependency para inyectar CreateTestCaseUseCase."""
    repository = TestCaseRepository(session)
    return CreateTestCaseUseCase(repository)


async def get_list_test_cases_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> ListTestCasesUseCase:
    """Dependency para inyectar ListTestCasesUseCase."""
    repository = TestCaseRepository(session)
    return ListTestCasesUseCase(repository)
