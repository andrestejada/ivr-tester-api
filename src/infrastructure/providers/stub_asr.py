"""Stub implementation of IASRProvider for testing purposes.

In HU-24, this will be replaced with a real Deepgram implementation.
"""

import logging
import os
import struct
from datetime import datetime

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
    Proveedor stub para testing mientras se implementa Deepgram (HU-24).
    
    Por ahora guarda el audio recibido localmente en .wav para debugging, 
    y retorna un string vacío (el orquestador mostrará texto no coincidente).
    """

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio (stub: guarda audio y retorna vacío).
        
        Args:
            audio_bytes: Buffer de audio mulaw a 8000Hz.
            
        Returns:
            String vacío (habrá timeout o mismatch de texto en tests)
        """
        # Guardar en local para que el desarrollador pueda escuchar el IVR
        try:
            os.makedirs("debug_audios", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"debug_audios/ivr_audio_{timestamp}.wav"
            
            with open(filepath, "wb") as f:
                f.write(build_mulaw_wav_header(len(audio_bytes)))
                f.write(audio_bytes)
                
            logger.info(f"🎧 Audio de Twilio guardado exitosamente en: {filepath}")
        except Exception as e:
            logger.error(f"Error al guardar debug de audio: {e}")

        logger.warning(
            "Using stub ASR provider - implement Deepgram in HU-24 "
            f"({len(audio_bytes)} audio bytes received, ignoring)"
        )
        return ""
