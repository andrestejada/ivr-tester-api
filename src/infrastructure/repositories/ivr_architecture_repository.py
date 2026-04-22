from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.application.exceptions import NotFoundError
from src.domain.repositories.ivr_architecture_repository import (
    IIVRArchitectureRepository,
)
from src.domain.entities.ivr_architecture import IVRArchitectureEntity
from src.infrastructure.database.models.ivr_architecture import IVRArchitectureModel


class IVRArchitectureRepository(IIVRArchitectureRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        phone_number: str,
        user_id: UUID,
        description: str | None = None,
    ) -> UUID:
        model = IVRArchitectureModel(
            name=name,
            phone_number=phone_number,
            user_id=user_id,
            description=description,
        )
        self.session.add(model)
        await self.session.flush()
        return model.id

    async def get_by_id(self, architecture_id: UUID) -> IVRArchitectureEntity:
        result = await self.session.execute(
            select(IVRArchitectureModel).where(
                IVRArchitectureModel.id == architecture_id
            )
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundError(f"IVR Architecture {architecture_id} not found")
        return self._to_entity(model)

    async def list_by_user(self, user_id: UUID) -> list[IVRArchitectureEntity]:
        result = await self.session.execute(
            select(IVRArchitectureModel).where(IVRArchitectureModel.user_id == user_id)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def delete(self, architecture_id: UUID, user_id: UUID) -> None:
        result = await self.session.execute(
            select(IVRArchitectureModel).where(
                (IVRArchitectureModel.id == architecture_id)
                & (IVRArchitectureModel.user_id == user_id)
            )
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundError(f"IVR Architecture {architecture_id} not found")
        await self.session.delete(model)

    async def update(
        self,
        architecture_id: UUID,
        user_id: UUID,
        name: str,
        phone_number: str,
        description: str | None = None,
    ) -> IVRArchitectureEntity | None:
        """Actualiza una IVR Architecture. Retorna None si no existe o no pertenece al usuario."""
        result = await self.session.execute(
            select(IVRArchitectureModel).where(
                (IVRArchitectureModel.id == architecture_id) &
                (IVRArchitectureModel.user_id == user_id)
            )
        )
        model = result.scalars().first()
        if not model:
            return None
        
        model.name = name
        model.phone_number = phone_number
        model.description = description
        model.updated_at = datetime.now(timezone.utc)  # Actualizar manualmente el timestamp
        
        await self.session.flush()
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: IVRArchitectureModel) -> IVRArchitectureEntity:
        return IVRArchitectureEntity(
            id=model.id,
            name=model.name,
            phone_number=model.phone_number,
            description=model.description,
            user_id=model.user_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            provider=model.provider,
        )
