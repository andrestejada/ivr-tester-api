from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.ivr_architecture import IVRArchitectureEntity


class IIVRArchitectureRepository(ABC):
    """Interfaz para el repositorio de IVR Architecture."""

    @abstractmethod
    async def create(
        self,
        name: str,
        phone_number: str,
        user_id: UUID,
        description: str | None = None,
    ) -> UUID:
        """Crea una nueva IVR Architecture."""
        pass

    @abstractmethod
    async def get_by_id(self, architecture_id: UUID) -> IVRArchitectureEntity:
        """Obtiene una IVR Architecture por ID."""
        pass

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[IVRArchitectureEntity]:
        """Lista arquitecturas IVR de un usuario."""
        pass

    @abstractmethod
    async def delete(self, architecture_id: UUID, user_id: UUID) -> None:
        """Elimina una IVR Architecture."""
        pass

    @abstractmethod
    async def update(
        self,
        architecture_id: UUID,
        user_id: UUID,
        name: str,
        phone_number: str,
        description: str | None = None,
    ) -> IVRArchitectureEntity | None:
        """Actualiza una IVR Architecture. Retorna None si no existe o no pertenece al usuario."""
        pass
