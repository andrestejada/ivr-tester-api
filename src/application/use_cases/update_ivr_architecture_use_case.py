from uuid import UUID
from src.domain.repositories.ivr_architecture_repository import (
    IIVRArchitectureRepository,
)
from src.domain.entities.ivr_architecture import IVRArchitectureEntity
from src.application.exceptions import NotFoundError


class UpdateIVRArchitectureUseCase:
    def __init__(self, repository: IIVRArchitectureRepository):
        self.repository = repository

    async def execute(
        self,
        architecture_id: UUID,
        user_id: UUID,
        name: str,
        phone_number: str,
        description: str | None = None,
    ) -> IVRArchitectureEntity:
        entity = await self.repository.update(
            architecture_id=architecture_id,
            user_id=user_id,
            name=name,
            phone_number=phone_number,
            description=description,
        )
        
        if entity is None:
            raise NotFoundError(f"IVR Architecture {architecture_id} not found")
        
        return entity
