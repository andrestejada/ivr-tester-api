from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class IVRArchitectureEntity:
    """Entidad de dominio para IVR Architecture."""

    id: UUID
    name: str
    phone_number: str
    user_id: UUID
    created_at: datetime
    provider: str = "twilio"  # Provider agnóstico: "twilio", "vonage", etc.
    updated_at: datetime | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 250:
            raise ValueError("El nombre debe tener entre 1 y 250 caracteres")
        if not self.phone_number.isdigit():
            raise ValueError("El teléfono debe contener solo números")
        if not self.provider:
            raise ValueError("El provider no puede estar vacío")
