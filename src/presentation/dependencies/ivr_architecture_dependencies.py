from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.application.use_cases import (
    CreateIVRArchitectureUseCase,
    DeleteIVRArchitectureUseCase,
    ListIVRArchitecturesUseCase,
    UpdateIVRArchitectureUseCase,
)
from src.infrastructure.call_session_store import get_call_session_store
from src.infrastructure.execution_event_hub import get_execution_event_hub
from src.infrastructure.repositories import (
    IVRArchitectureRepository,
    TestCaseRepository,
    TestExecutionRepository,
)
from src.infrastructure.database.session import get_db_session
from src.domain.repositories.ivr_architecture_repository import IIVRArchitectureRepository


async def get_ivr_architecture_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IIVRArchitectureRepository:
    """Inyecta repositorio de IVR Architectures."""
    return IVRArchitectureRepository(session)


async def get_create_ivr_architecture_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> CreateIVRArchitectureUseCase:
    repository = IVRArchitectureRepository(session)
    return CreateIVRArchitectureUseCase(repository)


async def get_list_ivr_architectures_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> ListIVRArchitecturesUseCase:
    repository = IVRArchitectureRepository(session)
    return ListIVRArchitecturesUseCase(repository)


async def get_update_ivr_architecture_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> UpdateIVRArchitectureUseCase:
    repository = IVRArchitectureRepository(session)
    return UpdateIVRArchitectureUseCase(repository)


async def get_delete_ivr_architecture_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> DeleteIVRArchitectureUseCase:
    architecture_repository = IVRArchitectureRepository(session)
    test_case_repository = TestCaseRepository(session)
    test_execution_repository = TestExecutionRepository(session)
    return DeleteIVRArchitectureUseCase(
        architecture_repository=architecture_repository,
        test_case_repository=test_case_repository,
        test_execution_repository=test_execution_repository,
        event_hub=get_execution_event_hub(),
        call_session_store=get_call_session_store(),
    )
