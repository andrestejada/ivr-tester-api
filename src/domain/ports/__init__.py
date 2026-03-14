"""Domain ports (interfaces) — abstracciones agnósticas."""

from src.domain.ports.call_provider import CallSession, ICallProvider
from src.domain.ports.asr_provider import IASRProvider

__all__ = [
    "CallSession",
    "ICallProvider",
    "IASRProvider",
]
