"""Port (interface) for ASR Provider — agnóstico de proveedor de transcripción."""

from abc import ABC, abstractmethod
from typing import Awaitable, Callable


class IASRProvider(ABC):
    """Interfaz agnóstica para proveedores de Auto Speech Recognition (ASR).
    
    Define el contrato para proveedores de streaming en tiempo real (Deepgram, Google Cloud, etc.)
    y también compatibilidad con modelos batch simples para testing.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Inicia la conexión de streaming con el servicio ASR.
        
        Esta llamada debe establecer la sesión en vivo contra el proveedor
        usando las credenciales configuradas.
        
        Raises:
            Exception: Si no se puede conectar o falta la API Key.
        """
        pass

    @abstractmethod
    async def set_transcript_handler(
        self, callback: Callable[[str, bool, bool], Awaitable[None]]
    ) -> None:
        """Registra un callback para recibir transcripciones parciales y finales.
        
        Args:
            callback: fn(texto: str, is_final: bool, speech_final: bool)
        """
        pass

    @abstractmethod
    async def send_audio(self, chunk: bytes) -> None:
        """Envía un fragmento de audio al stream en vivo.
        
        Args:
            chunk: Buffer de audio en formato mulaw (8kHz, mono).
            
        Raises:
            Exception: Si no hay conexión activa o error al transmitir.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Cierra la conexión ASR de forma segura.
        
        Debe finalizar la sesión en vivo y liberar recursos.
        """
        pass

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe un buffer de audio a texto (compatibilidad batch/simplifucada).
        
        Este método se proporciona para compatibilidad con casos de uso que necesitan
        transcripción simple sin streaming. Las implementaciones pueden ignorar este
        método si usan el modelo de streaming (connect/send_audio/callbacks).
        
        Args:
            audio_bytes: Buffer de audio en formato mulaw (8kHz, mono).
            
        Returns:
            Texto transcrito (string).
            
        Raises:
            Exception: Si hay error de transcripción.
        """
        pass
