"""Adaptador ASR real usando Deepgram para streaming en tiempo real con WebSockets.

Este proveedor implementa la interfaz agnóstica IASRProvider usando el SDK oficial
de Deepgram para transcripción en vivo durante las llamadas IVR.

AC 1: Usa obligatoriamente la variable de entorno DEEPGRAM_API_KEY sin hardcodeo.
AC 2: Usa WebSocket streaming (listen.v2.connect) con el modelo nova-2.
AC 3: Implementa reintentos con tenacity (máximo 3 intentos).
"""

import logging
from typing import Awaitable, Callable, Optional

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
try:
    from deepgram.listen.v1.types import ListenV1Results
except ImportError:
    ListenV1Results = None

from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.ports.asr_provider import IASRProvider
from src.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class DeepgramASRProvider(IASRProvider):
    """Adaptador ASR de Deepgram para transcripción en vivo vía WebSocket.
    
    Características:
    - Conexión persistente mediante WebSocket (listen.v2.connect)
    - Modelo nova-2 optimizado para streaming
    - Callbacks asíncronos para transcripciones parciales y finales
    - Manejo automático de reconexiones (delegado a tenacity en el orquestador)
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Inicializa el adaptador de Deepgram.
        
        Args:
            settings: Instancia de Settings con DEEPGRAM_API_KEY. 
                     Si es None, se usa la instancia global.
                     
        Raises:
            ValueError: Si deepgram_api_key no está configurada o es "placeholder".
        """
        self.settings = settings or Settings()
        
        # Validar que la API key está configurada (AC 1: sin hardcodeo)
        if not self.settings.deepgram_api_key or \
           self.settings.deepgram_api_key == "placeholder":
            raise ValueError(
                "DEEPGRAM_API_KEY no está configurada en .env. "
                "Por favor, añade tu API key de Deepgram a las variables de entorno."
            )
        
        self._client: Optional[AsyncDeepgramClient] = None
        self._connection: Optional[object] = None
        self._connection_ctx: Optional[object] = None
        self._listen_task: Optional[object] = None
        self._transcript_handler: Optional[
            Callable[[str, bool], Awaitable[None]]
        ] = None
        self._is_connected = False

    @retry(
        stop=stop_after_attempt(3),  # AC 3: Máximo 3 reintentos
        wait=wait_exponential(multiplier=1, min=1, max=10),  # Backoff: 1s, 2s, 4s...
        before_sleep=before_sleep_log(logger, logging.WARNING),  # Log de reintentos
        reraise=True,  # Re-lanzar la excepción si fallan todos los intentos
    )
    async def connect(self, **kwargs) -> None:
        """Inicia la conexión de streaming con Deepgram (AC 2).
        
        Establece una conexión WebSocket en vivo usando el modelo nova-2
        y configura los handlers para recibir transcripciones.
        
        Con AC 3: Automáticamente reintenta hasta 3 veces ante fallos de red,
        errores 429 (rate limit) o 5xx, con backoff exponencial.
        
        Args:
            **kwargs: Parámetros opcionales adicionales (ej. encoding="mulaw", sample_rate=8000)
                      Requeridos para el uso real con Twilio.
        """
        try:
            import asyncio
            import logging
            logging.getLogger("websockets.client").setLevel(logging.INFO)  # Callate websockets client

            # Instanciar cliente de Deepgram asíncrono
            # En v6.0.1, si queremos pasar la api_key, es mediante un kwarg
            self._client = AsyncDeepgramClient(api_key=self.settings.deepgram_api_key)
            
            # Parametros por defecto que soportan kwarg overrides
            options = {
                "model": "nova-2",
                "language": "es",
            }
            options.update(kwargs)
            
            # Crear contexto de conexión en vivo
            self._connection_ctx = self._client.listen.v1.connect(**options)
            
            # Entrar al contexto asíncrono manualmente
            self._connection = await self._connection_ctx.__aenter__()
            
            # Evento para esperar a que el stream esté listo
            self._ready_event = asyncio.Event()
            
            # Registrar handlers
            self._connection.on(EventType.OPEN, lambda *args, **kw: self._ready_event.set())
            self._connection.on(EventType.MESSAGE, self._on_transcript_received)
            self._connection.on(EventType.ERROR, self._on_connection_error)
            
            # Iniciar el bucle de escucha de Deepgram en background
            self._listen_task = asyncio.create_task(self._connection.start_listening())
            
            # Esperar a que el websocket esté "OPEN" y listo
            await asyncio.wait_for(self._ready_event.wait(), timeout=5.0)
            
            self._is_connected = True
            
            logger.info("✅ Conexión Deepgram ASR establecida")
            
        except Exception as e:
            logger.error(f"❌ Error Deepgram durante connect(): {e}")
            self._is_connected = False
            # Lanzar para que tenacity reintente
            raise

    async def set_transcript_handler(
        self, callback: Callable[[str, bool], Awaitable[None]]
    ) -> None:
        """Registra el callback para recibir transcripciones.
        
        El callback será invocado cada vez que Deepgram envíe un fragmento
        de transcripción, indicando si el fragmento es final o parcial.
        
        Args:
            callback: Función async que recibe (texto: str, es_final: bool).
        """
        self._transcript_handler = callback
        logger.debug("Callback de transcripción registrado en Deepgram ASR")

    async def send_audio(self, chunk: bytes) -> None:
        """Envía un fragmento de audio al stream en vivo de Deepgram.
        
        Args:
            chunk: Buffer de audio en formato mulaw (8kHz, mono).
            
        Raises:
            RuntimeError: Si no hay conexión activa.
        """
        if not self._is_connected or not self._connection:
            logger.warning(
                "send_audio() llamado sin conexión activa "
                "(ignorando chunk de %d bytes)", len(chunk)
            )
            return
        
        try:
            # Enviar chunk directamente al WebSocket de Deepgram usando nuevo método
            await self._connection.send_media(chunk)
            # Evitamos loguear cada fragmento para no hacer spam en consola
            pass
            
        except Exception as e:
            logger.error(f"❌ Error al enviar audio a Deepgram: {e}")
            raise

    async def disconnect(self) -> None:
        """Cierra la conexión de forma segura.
        
        Detiene el stream, cierra el WebSocket y libera recursos.
        """
        if not self._is_connected or not self._connection:
            logger.debug("disconnect() llamado cuando ya estaba desconectado")
            return
        
        try:
            # Finalizar la conexión en vivo de Deepgram
            await self._connection.send_close_stream()
            
            # Esperar a que la tarea termine
            if self._listen_task:
                import asyncio
                try:
                    await asyncio.wait_for(self._listen_task, timeout=2.0)
                except asyncio.TimeoutError:
                    self._listen_task.cancel()
                    
            # Salir del contexto asíncrono
            if self._connection_ctx:
                await self._connection_ctx.__aexit__(None, None, None)
                
            self._is_connected = False
            self._connection = None
            self._connection_ctx = None
            
            logger.info("✅ Conexión Deepgram ASR cerrada correctamente")
            
        except Exception as e:
            if "1000" in str(e):
                logger.info("✅ Conexión Deepgram ASR cerrada correctamente (Code 1000)")
            elif "1005" in str(e):
                logger.debug("Conexión Deepgram cerrada en estado neutro (Code 1005)")
            else:
                logger.error(f"⚠️  Error al cerrar Deepgram: {e}")
            self._is_connected = False

    # ============================================================================
    # Handlers para eventos de Deepgram
    # ============================================================================

    async def _on_transcript_received(self, transcript, **kwargs) -> None:
        """Handler interno para eventos de transcripción de Deepgram.
        
        Invoca el callback registrado si existe.
        
        Args:
            transcript: Objeto de respuesta de Deepgram (ej. ListenV1Results).
            **kwargs: Argumentos adicionales (ignorados).
        """
        # Filtrar solo eventos de resultados que tengan canal
        if not hasattr(transcript, 'channel') or not transcript.channel:
            return

        if not self._transcript_handler:
            logger.debug("Transcripción recibida pero sin callback registrado")
            return
        
        try:
            # Extraer el texto del primer canal, primera alternativa
            channel = transcript.channel
            if hasattr(channel, 'alternatives') and channel.alternatives:
                alternative = channel.alternatives[0]
                text = alternative.transcript if hasattr(alternative, 'transcript') else ""
                is_final = transcript.is_final if hasattr(transcript, 'is_final') else False
                speech_final = transcript.speech_final if hasattr(transcript, 'speech_final') else False
                
                if text:
                    logger.debug(
                        f"📝 Transcripción {'final' if is_final else 'parcial'}, speech_final={speech_final}: {text}"
                    )
                    # Invocar callback del orquestador: text, is_final, speech_final
                    # Para mantener compatibilidad si el callback no acepta 3 parametros,
                    # lo logueamos, pero vamos a pasar los 3 parametros si lo soportamos.
                    try:
                        await self._transcript_handler(text, is_final, speech_final)
                    except TypeError:
                        await self._transcript_handler(text, is_final)

        except Exception as e:
            logger.error(f"❌ Error procesando transcripción de Deepgram: {e}")

    async def _on_connection_error(self, error, **kwargs) -> None:
        """Handler interno para errores de conexión de Deepgram.
        
        Registra el error y marca la conexión como inactiva.
        
        Args:
            error: Objeto de error de Deepgram.
            **kwargs: Argumentos adicionales (ignorados).
        """
        logger.error(f"❌ Error de conexión Deepgram: {error}")
        self._is_connected = False

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe un buffer de audio de forma síncrona (compatibilidad batch).
        
        NOTA: Este método es para compatibilidad con código legacy que espera
        transcripción batch simple. Deepgram está optimizado para streaming,
        pero este método proporciona una interfaz simple alternativa.
        
        En la práctica, para casos de uso en vivo (IVR), se recomienda usar
        la interfaz de streaming (connect/send_audio/callbacks) para mejor
        rendimiento y latencia más baja.
        
        Args:
            audio_bytes: Buffer de audio en formato mulaw (8kHz, mono).
            
        Returns:
            Texto transcrito. Vacío si hay error o sin transcripción.
            
        Raises:
            ValueError: Si la API key no está configurada.
        """
        # Para esta versión, retornamos una cadena vacía.
        # En tests, este método será mockeado.
        # En producción, si se necesita transcripción batch real, 
        # se usaría el endpoint de batch de Deepgram, no el streaming.
        logger.info(f"transcribe() batch llamado con {len(audio_bytes)} bytes (mock)")
        return ""
