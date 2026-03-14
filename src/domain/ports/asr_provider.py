"""Port (interface) for ASR Provider — agnóstico de proveedor de transcripción."""

from abc import ABC, abstractmethod


class IASRProvider(ABC):
    """Interfaz agnóstica para proveedores de Auto Speech Recognition (ASR).
    
    Define el contrato para transcribir audio a texto (Deepgram, Google Cloud Speech, etc.)
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe un buffer de audio a texto.
        
        Args:
            audio_bytes: Buffer de audio en formato mulaw (8kHz, mono)
            
        Returns:
            Texto transcrito (string)
            
        Raises:
            Exception si hay error de conexión, formato inválido, etc.
        """
        pass
