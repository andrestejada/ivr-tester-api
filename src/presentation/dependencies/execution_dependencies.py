"""Dependency injection for Test Execution components."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.use_cases.execute_test_case_use_case import ExecuteTestCaseUseCase
from src.domain.repositories.test_case_repository import ITestCaseRepository
from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.domain.repositories.execution_log_repository import IExecutionLogRepository
from src.infrastructure.call_session_store import get_call_session_store
from src.infrastructure.database.session import async_session_maker, get_db_session
from src.infrastructure.database.uow import UnitOfWork
from src.infrastructure.repositories.test_case_repository import TestCaseRepository
from src.infrastructure.repositories.test_execution_repository import TestExecutionRepository
from src.infrastructure.repositories.execution_log_repository import ExecutionLogRepository
from src.infrastructure.providers.twilio import TwilioCallProvider
from src.infrastructure.providers.deepgram_asr_provider import DeepgramASRProvider


async def get_test_case_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ITestCaseRepository:
    """Inyecta repositorio de test cases."""
    return TestCaseRepository(session)


async def get_test_execution_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ITestExecutionRepository:
    """Inyecta repositorio de ejecuciones."""
    return TestExecutionRepository(session)


async def get_execution_log_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IExecutionLogRepository:
    """Inyecta repositorio de logs."""
    return ExecutionLogRepository(session)


async def get_execute_test_case_use_case(
    test_case_repo: ITestCaseRepository = Depends(get_test_case_repo),
    test_execution_repo: ITestExecutionRepository = Depends(get_test_execution_repo),
    execution_log_repo: IExecutionLogRepository = Depends(get_execution_log_repo),
) -> ExecuteTestCaseUseCase:
    """Inyecta el use case con todas sus dependencias.
    
    Nota: Requiere DEEPGRAM_API_KEY en .env.
    """
    return ExecuteTestCaseUseCase(
        test_case_repo=test_case_repo,
        test_execution_repo=test_execution_repo,
        execution_log_repo=execution_log_repo,
        call_provider=TwilioCallProvider(),
        asr_provider=DeepgramASRProvider(),
        call_session_store=get_call_session_store(),
        uow_factory=lambda: UnitOfWork(async_session_maker),
    )
