"""Execution Log domain entity — log de un step de ejecución de test case."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class ExecutionLogEntity:
    """Entidad de dominio para el log de un paso de ejecución."""

    id: UUID
    execution_id: UUID
    step_number: int
    expected_text: str | None
    actual_transcription: str | None
    confidence_score: Decimal | None
    action_taken: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        """Validaciones de invariantes de dominio."""
        if self.step_number < 1:
            raise ValueError("step_number debe ser ≥ 1")
        
        if self.confidence_score is not None:
            if not (Decimal("0") <= self.confidence_score <= Decimal("100")):
                raise ValueError("confidence_score debe estar entre 0 y 100")
