"""Dependency injection for Test Case use cases."""

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.application.use_cases import (
    CreateTestCaseUseCase,
    DeleteTestCaseUseCase,
    ListTestCasesUseCase,
    UpdateTestCaseUseCase,
)
from src.infrastructure.call_session_store import get_call_session_store
from src.infrastructure.execution_event_hub import get_execution_event_hub
from src.infrastructure.repositories import (
    IVRArchitectureRepository,
    TestCaseRepository,
    TestExecutionRepository,
)
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


async def get_update_test_case_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> UpdateTestCaseUseCase:
    """Dependency para inyectar UpdateTestCaseUseCase."""
    repository = TestCaseRepository(session)
    return UpdateTestCaseUseCase(repository)


async def get_delete_test_case_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> DeleteTestCaseUseCase:
    """Dependency para inyectar DeleteTestCaseUseCase."""
    architecture_repository = IVRArchitectureRepository(session)
    test_case_repository = TestCaseRepository(session)
    test_execution_repository = TestExecutionRepository(session)
    return DeleteTestCaseUseCase(
        architecture_repository=architecture_repository,
        test_case_repository=test_case_repository,
        test_execution_repository=test_execution_repository,
        event_hub=get_execution_event_hub(),
        call_session_store=get_call_session_store(),
    )
