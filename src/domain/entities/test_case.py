"""Test Case entity — a test script (flow) for a specific IVR architecture."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class TestCaseEntity:
    """Entidad de dominio para Test Case."""

    id: UUID
    ivr_architecture_id: UUID
    name: str
    flow_script: list[dict]
    created_at: datetime

    def __post_init__(self) -> None:
        """Validaciones invariantes del dominio."""
        if not self.name or len(self.name) > 255:
            raise ValueError("El nombre debe tener entre 1 y 255 caracteres")
        if not isinstance(self.flow_script, list) or len(self.flow_script) == 0:
            raise ValueError("flow_script debe ser una lista no vacía")
