"""Twilio implementation of ICallProvider."""

import asyncio
from typing import Optional

from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.domain.ports.call_provider import ICallProvider, CallSession
from src.infrastructure.config import settings
from src.infrastructure.logger import get_logger
from src.application.utils.error_utils import classify_error_category

logger = get_logger(__name__)


def _is_network_error_retryable(error: Exception) -> bool:
    """
    Determine if an error is a transient network error worth retrying.
    
    Returns True for DNS, connection, and timeout errors.
    Returns False for auth, credential, and permanent errors.
    """
    error_category = classify_error_category(error)
    return error_category in ('network', 'timeout', 'unavailable')


class TwilioCallProvider(ICallProvider):
    """
    Adaptador concreto de Twilio para el puerto ICallProvider.
    
    Implementa las acciones de telefonía usando Twilio Python SDK.
    """

    def __init__(self) -> None:
        """Inicializa el proveedor con credenciales de Twilio."""
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_phone_number
        
        # Importar aquí para no contaminar domain/
        try:
            from twilio.rest import Client
            self.client = Client(self.account_sid, self.auth_token)
        except ImportError:
            logger.error("twilio package not installed")
            raise

    async def initiate_call(
        self, phone_number: str, webhook_url: str
    ) -> CallSession:
        """Inicia una llamada via Twilio REST API con reintentos para fallos transitorios.
        
        Reintentos automáticos para:
        - Errores DNS/resolución de nombres (ej: NameResolutionError)
        - Timeouts de conexión
        - Fallos temporales de disponibilidad del servicio
        
        No reintenta para:
        - Errores de autenticación
        - Números inválidos
        - Errores de configuración
        
        Args:
            phone_number: Número a marcar (ej: "+1234567890")
            webhook_url: URL del webhook que Twilio llamará
            
        Returns:
            CallSession con call_sid asignado
            
        Raises:
            Exception si luego de 3 reintentos el error persiste o es no-reintentable
        """
        max_retries = 3
        retry_delay = 1  # seconds
        attempt = 0
        
        while attempt < max_retries:
            try:
                attempt += 1
                logger.info(
                    f"Initiating call to {phone_number} (attempt {attempt}/{max_retries})"
                )
                
                # Crear llamada via Twilio REST API
                call = self.client.calls.create(
                    to=phone_number,
                    from_=self.from_number,
                    url=webhook_url,
                    method="POST",
                )
                
                logger.info(f"Call created with SID: {call.sid}")
                return CallSession(call_sid=call.sid)
            
            except Exception as e:
                error_msg = str(e)
                error_category = classify_error_category(e)
                
                # Log completo con stack trace para el telemetry backend
                logger.error(
                    f"Error initiating call (attempt {attempt}/{max_retries}): {error_msg}",
                    exc_info=True,
                    extra={
                        "error_category": error_category,
                        "phone_number": phone_number,
                        "attempt": attempt,
                    }
                )
                
                # Si no es reintentable o es el último intento, lanzar
                if not _is_network_error_retryable(e) or attempt >= max_retries:
                    logger.warning(
                        f"Call initiation failed (category={error_category}, reintentable={_is_network_error_retryable(e)}). "
                        f"Not retrying."
                    )
                    raise
                
                # Esperar antes de reintentar con backoff exponencial
                wait_time = retry_delay * (2 ** (attempt - 1))  # 1s, 2s, 4s
                logger.info(f"Retrying call initiation in {wait_time}s...")
                await asyncio.sleep(wait_time)

    async def send_dtmf(self, call_sid: str, digits: str) -> None:
        """Envía DTMF vía update de llamada.
        
        En Twilio, esto se logra actualizando el call con un Twiml que
        incluya <Play digits="..."/> y reinicia el stream.
        
        Args:
            call_sid: ID de la llamada
            digits: Dígitos a enviar
            
        Raises:
            Exception si la llamada no existe o ya terminó
        """
        try:
            from twilio.twiml.voice_response import VoiceResponse, Play, Start, Stream, Pause
            
            logger.info(f"Sending DTMF {digits} to call {call_sid}")
            
            # Extraer dominio para formar la URL segura del WebSocket (wss)
            domain = settings.base_url.replace("http://", "").replace("https://", "").rstrip("/")
            scheme = "wss" if "https" in settings.base_url else "ws"
            ws_url = f"{scheme}://{domain}/ws/call/{call_sid}"
            
            # Construir el TwiML de forma segura usando el SDK oficial:
            response = VoiceResponse()
            
            # 1. <Play digits="ww{digits}">: los 'ww' agregan 1 segundo de pausa antes de marcar
            response.play(digits=f"ww{digits}")
            
            # 2. <Start><Stream ...>: reabre la conexión WebSocket
            start = Start()
            start.stream(name="ivr_stream", url=ws_url, track="inbound_track")
            response.append(start)
            
            # 3. <Pause length="3600"/>: mantiene la llamada transcurriendo
            response.pause(length=3600)

            twiml_string = str(response)

            # Realiza la modificación de la llamada en tiempo real a través de la API REST
            self.client.calls(call_sid).update(twiml=twiml_string)
            logger.info(f"Successfully sent DTMF {digits} and reopened stream for {call_sid}")
            
        except Exception as e:
            logger.error(f"Error sending DTMF: {e}")
            raise

    async def hangup(self, call_sid: str) -> None:
        """Cuelga una llamada.
        
        Args:
            call_sid: ID de la llamada a terminar
            
        Raises:
            Exception si la llamada no existe
        """
        try:
            logger.info(f"Hanging up call {call_sid}")
            self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call {call_sid} hung up")
        
        except Exception as e:
            logger.error(f"Error hanging up call: {e}")
            raise
