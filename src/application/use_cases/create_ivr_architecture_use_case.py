from uuid import UUID
from src.domain.repositories.ivr_architecture_repository import (
    IIVRArchitectureRepository,
)


class CreateIVRArchitectureUseCase:
    def __init__(self, repository: IIVRArchitectureRepository):
        self.repository = repository

    async def execute(
        self,
        name: str,
        phone_number: str,
        user_id: UUID,
        description: str | None = None,
    ) -> UUID:
        return await self.repository.create(
            name=name,
            phone_number=phone_number,
            user_id=user_id,
            description=description,
        )
