"""Twilio implementation of ICallProvider."""

import logging
from typing import Optional

from src.domain.ports.call_provider import ICallProvider, CallSession
from src.infrastructure.config import settings

logger = logging.getLogger(__name__)


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
        """Inicia una llamada via Twilio REST API.
        
        Args:
            phone_number: Número a marcar (ej: "+1234567890")
            webhook_url: URL del webhook que Twilio llamará
            
        Returns:
            CallSession con call_sid asignado
            
        Raises:
            Exception si el número es inválido, cuenta sin crédito, etc.
        """
        try:
            logger.info(f"Initiating call to {phone_number}")
            
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
            logger.error(f"Error initiating call: {e}")
            raise

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
            
            # 3. <Pause length="60"/>: mantiene la llamada transcurriendo
            response.pause(length=60)

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
