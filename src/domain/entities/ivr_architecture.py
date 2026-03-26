from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
import re


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
        # Permitir números, +, espacios y guiones (formato internacional)
        if not re.match(r"^\+?[\d\s-]+$", self.phone_number):
            raise ValueError("El teléfono debe contener solo números, +, espacios o guiones")
        if not self.provider:
            raise ValueError("El provider no puede estar vacío")
