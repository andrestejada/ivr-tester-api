"""DTOs para eventos de ejecución en tiempo real.

Define el contrato v1 de eventos que se emiten durante la ejecución de un test case.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class ExecutionEventType(str, Enum):
    """Tipos de eventos que puede emitir una ejecución."""

    EXECUTION_STARTED = "execution_started"
    STATUS_CHANGED = "status_changed"
    TRANSCRIPT_PARTIAL = "transcript_partial"
    TRANSCRIPT_FINAL = "transcript_final"
    STEP_STARTED = "step_started"
    STEP_MATCHED = "step_matched"
    STEP_FAILED = "step_failed"
    STEP_LOGGED = "step_logged"
    EXECUTION_FINISHED = "execution_finished"
    EXECUTION_ERROR = "execution_error"


@dataclass
class ExecutionEvent:
    """Envolvente estándar para eventos de ejecución.
    
    Proporciona consistencia en formato, timestamp y trazabilidad.
    """

    event_type: ExecutionEventType
    execution_id: UUID
    timestamp: datetime
    data: dict[str, Any]
    schema_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        """Serializa el evento a dict para envío por WebSocket."""
        return {
            "event_type": self.event_type.value,
            "execution_id": str(self.execution_id),
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "schema_version": self.schema_version,
        }

    @staticmethod
    def execution_started(execution_id: UUID) -> "ExecutionEvent":
        """Evento: ejecución inicia."""
        return ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_STARTED,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={"status": "RUNNING"},
        )

    @staticmethod
    def status_changed(execution_id: UUID, old_status: str, new_status: str) -> "ExecutionEvent":
        """Evento: cambio de estado."""
        return ExecutionEvent(
            event_type=ExecutionEventType.STATUS_CHANGED,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={"old_status": old_status, "new_status": new_status},
        )

    @staticmethod
    def transcript_partial(execution_id: UUID, text: str) -> "ExecutionEvent":
        """Evento: transcripción parcial del ASR."""
        return ExecutionEvent(
            event_type=ExecutionEventType.TRANSCRIPT_PARTIAL,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={"text": text, "is_final": False},
        )

    @staticmethod
    def transcript_final(execution_id: UUID, text: str) -> "ExecutionEvent":
        """Evento: transcripción final del ASR."""
        return ExecutionEvent(
            event_type=ExecutionEventType.TRANSCRIPT_FINAL,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={"text": text, "is_final": True},
        )

    @staticmethod
    def step_started(execution_id: UUID, step_number: int, expected_text: str) -> "ExecutionEvent":
        """Evento: inicio de un paso."""
        return ExecutionEvent(
            event_type=ExecutionEventType.STEP_STARTED,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={"step_number": step_number, "expected_text": expected_text},
        )

    @staticmethod
    def step_matched(
        execution_id: UUID,
        step_number: int,
        matched_text: str,
        confidence: float,
    ) -> "ExecutionEvent":
        """Evento: paso coincidió con transcripción."""
        return ExecutionEvent(
            event_type=ExecutionEventType.STEP_MATCHED,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={
                "step_number": step_number,
                "matched_text": matched_text,
                "confidence": confidence,
            },
        )

    @staticmethod
    def step_failed(
        execution_id: UUID,
        step_number: int,
        expected_text: str,
        actual_text: Optional[str],
        reason: str,
    ) -> "ExecutionEvent":
        """Evento: paso falló."""
        return ExecutionEvent(
            event_type=ExecutionEventType.STEP_FAILED,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={
                "step_number": step_number,
                "expected_text": expected_text,
                "actual_text": actual_text,
                "reason": reason,
            },
        )

    @staticmethod
    def step_logged(execution_id: UUID, step_number: int) -> "ExecutionEvent":
        """Evento: log del paso fue persistido en BD."""
        return ExecutionEvent(
            event_type=ExecutionEventType.STEP_LOGGED,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={"step_number": step_number},
        )

    @staticmethod
    def execution_finished(
        execution_id: UUID,
        status: str,
        duration_seconds: int,
    ) -> "ExecutionEvent":
        """Evento: ejecución finalizó exitosamente."""
        return ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_FINISHED,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={"status": status, "duration_seconds": duration_seconds},
        )

    @staticmethod
    def execution_error(
        execution_id: UUID,
        error_message: str,
        duration_seconds: int,
    ) -> "ExecutionEvent":
        """Evento: ejecución terminó con error."""
        return ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_ERROR,
            execution_id=execution_id,
            timestamp=datetime.now(timezone.utc),
            data={
                "status": "ERROR",
                "error_message": error_message,
                "duration_seconds": duration_seconds,
            },
        )
