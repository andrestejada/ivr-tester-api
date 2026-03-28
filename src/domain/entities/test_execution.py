"""Test Execution domain entity — a single run of a test case."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class TestExecutionEntity:
    """Entidad de dominio para la ejecución de un test case."""

    id: UUID
    test_case_id: UUID
    status: str
    duration_seconds: int | None
    provider_call_sid: str | None
    executed_at: datetime
    full_call_transcript: str | None = None

    def __post_init__(self) -> None:
        # basic invariants
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds no puede ser negativo")
        if self.status not in ("RUNNING", "PASSED", "FAILED", "ERROR"):
            raise ValueError("status inválido para TestExecutionEntity")
