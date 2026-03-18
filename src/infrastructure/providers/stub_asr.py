"""Stub implementation of IASRProvider for testing purposes.

In HU-25, this will be replaced with a real Deepgram implementation.
Compatible with the new streaming-based IASRProvider interface.
"""

import logging
import os
import struct
from datetime import datetime
from typing import Awaitable, Callable, Optional

from src.domain.ports.asr_provider import IASRProvider

logger = logging.getLogger(__name__)


def build_mulaw_wav_header(data_size: int) -> bytes:
    """Construye un header WAV válido para audio mulaw (8kHz, 1-canal, 8-bit)."""
    header = struct.pack('<4sI4s', b'RIFF', 46 + data_size, b'WAVE')
    # fmt chunk
    header += struct.pack('<4sIHHIIHH', b'fmt ', 16, 7, 1, 8000, 8000, 1, 8)
    # fact chunk (necesario para formatos no PCM como mulaw)
    header += struct.pack('<4sII', b'fact', 4, data_size)
    # data chunk
    header += struct.pack('<4sI', b'data', data_size)
    return header


class StubASRProvider(IASRProvider):
    """
    Proveedor stub para testing mientras se implementa Deepgram (HU-25).
    
    Soporta la interfaz de streaming agnóstica.
    Guardar el audio recibido localmente en .wav para debugging, 
    sin invocar el callback (no simula transcripciones).
    """

    def __init__(self) -> None:
        """Inicializa el proveedor stub."""
        self._transcript_handler: Optional[
            Callable[[str, bool], Awaitable[None]]
        ] = None
        self._is_connected = False
        self._audio_buffer = bytearray()

    async def connect(self) -> None:
        """Stub: marca la conexión como activa.
        
        No realiza conectividad real.
        """
        self._is_connected = True
        self._audio_buffer = bytearray()
        logger.info("Stub ASR: conexión marcada como activa")

    async def set_transcript_handler(
        self, callback: Callable[[str, bool], Awaitable[None]]
    ) -> None:
        """Registra el callback para transcripciones (stub).
        
        Args:
            callback: Función que recibirá el texto transcrito.
        """
        self._transcript_handler = callback
        logger.info("Stub ASR: callback de transcripción registrado")

    async def send_audio(self, chunk: bytes) -> None:
        """Stub: almacena bytes en un buffer local y guarda archivo .wav.
        
        Args:
            chunk: Buffer de audio mulaw a 8000Hz.
        """
        if not self._is_connected:
            logger.warning("Stub ASR: intentando enviar audio sin conexión")
            return

        self._audio_buffer.extend(chunk)

        # Guardar en local para que el desarrollador pueda escuchar el IVR
        try:
            os.makedirs("debug_audios", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"debug_audios/ivr_audio_{timestamp}.wav"

            with open(filepath, "wb") as f:
                f.write(build_mulaw_wav_header(len(self._audio_buffer)))
                f.write(bytes(self._audio_buffer))

            logger.debug(
                f"🎧 Audio de Twilio guardado en: {filepath} "
                f"({len(self._audio_buffer)} bytes)"
            )
        except Exception as e:
            logger.error(f"Error al guardar debug de audio: {e}")

    async def disconnect(self) -> None:
        """Stub: marca la conexión como inactiva."""
        self._is_connected = False
        self._audio_buffer = bytearray()
        logger.info("Stub ASR: conexión cerrada")

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Stub: retorna una cadena vacía (sin transcripción real).
        
        Este método es para compatibilidad con código que espera
        el modelo batch simple. El stub no realiza transcripción
        porque es para testing sin dependencias externas.
        
        Args:
            audio_bytes: Buffer de audio a transcribir (ignorado en stub).
            
        Returns:
            String vacío (el test debe mockear este método).
        """
        logger.info(f"Stub ASR: transcribe() llamado con {len(audio_bytes)} bytes")
        return ""
