from uuid import UUID

from src.application.dtos import IVRArchitectureResponse
from src.domain.repositories.ivr_architecture_repository import (
    IIVRArchitectureRepository,
)
from src.domain.entities.ivr_architecture import IVRArchitectureEntity


class ListIVRArchitecturesUseCase:
    def __init__(self, repository: IIVRArchitectureRepository):
        self.repository = repository

    async def execute(self, user_id: UUID) -> list[IVRArchitectureResponse]:
        architectures = await self.repository.list_by_user(user_id)
        return [
            IVRArchitectureResponse(
                id=arch.id,
                name=arch.name,
                phone_number=arch.phone_number,
                description=arch.description,
                provider=arch.provider,
                created_at=arch.created_at,
            )
            for arch in architectures
        ]
