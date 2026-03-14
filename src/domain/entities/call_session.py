"""Call Session domain entity — sesión activa de una llamada telefónica."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CallSessionEntity:
    """Entidad de dominio para una sesión de llamada telefónica activa.
    
    Representa el estado de una llamada en curso con datos puros de negocio.
    La gestión de colas de audio (asyncio.Queue) pertenece a la capa de
    infraestructura (CallSessionStore).
    """

    call_sid: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = field(default=True)

    def __post_init__(self) -> None:
        """Validaciones de invariantes."""
        if not self.call_sid or not self.call_sid.strip():
            raise ValueError("call_sid no puede estar vacío")
