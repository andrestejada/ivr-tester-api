"""Proveedores de infraestructura (ASR, Call providers, etc.)."""

from src.infrastructure.providers.deepgram_asr_provider import (
    DeepgramASRProvider,
)
from src.infrastructure.providers.stub_asr import StubASRProvider

__all__ = [
    "DeepgramASRProvider",
    "StubASRProvider",
]
