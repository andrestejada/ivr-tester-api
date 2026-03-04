from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.application.use_cases import CreateIVRArchitectureUseCase, ListIVRArchitecturesUseCase
from src.infrastructure.repositories import IVRArchitectureRepository
from src.infrastructure.database.session import get_db_session


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
