"""Webhook endpoint for Twilio voice calls."""

import logging
from fastapi import APIRouter, Request, HTTPException, Response

from src.infrastructure.providers.twilio import TwilioWebhookValidator
from src.infrastructure.config import settings
from src.infrastructure.call_session_store import get_call_session_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

# Inicializar validador
_webhook_validator = TwilioWebhookValidator(settings.twilio_auth_token)


@router.post("/webhooks/twilio/voice")
async def twilio_voice_webhook(request: Request) -> Response:
    """
    Webhook que Twilio llama cuando inicia una llamada.
    
    Válida la firma de Twilio (OWASP security best practice).
    Responde con TwiML que inicia un stream de audio.
    
    Returns:
        TwiML XML para que Twilio inicie el stream
    """
    try:
        logger.info(
            "Twilio webhook received: method=%s url=%s client=%s",
            request.method,
            str(request.url),
            request.client,
        )
        # Leer el cuerpo para obtener los parámetros
        form_data = await request.form()
        data_dict = dict(form_data)
        
        # Obtener la firma del header
        signature_header = request.headers.get("X-Twilio-Signature", "")
        
        # Validar firma (con bypass opcional en development)
        url = str(request.url)
        logger.debug(
            "Twilio webhook debug: url=%s signature_present=%s form_keys=%s",
            url,
            bool(signature_header),
            list(data_dict.keys()),
        )

        if settings.app_env.lower() == "development":
            is_valid = True
            logger.warning("Twilio signature validation bypassed (development)")
        else:
            is_valid = _webhook_validator.validate_signature(
                url=url,
                data=data_dict,
                signature_header=signature_header
            )
        
        if not is_valid:
            logger.warning(f"Invalid Twilio signature from {request.client}")
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        logger.info(f"Valid Twilio webhook call received")
        
        # Extraer el CallSid del request
        call_sid = data_dict.get("CallSid")
        if not call_sid:
            logger.error("No CallSid in webhook request")
            raise HTTPException(status_code=400, detail="Missing CallSid")
        
        # Crear sesión en el store
        store = get_call_session_store()
        await store.create_session(call_sid)
        logger.info(f"Session created for call {call_sid}")
        
        # Construir base URL para el WebSocket
        base_url = settings.base_url or f"{request.base_url.rstrip('/')}"
        ws_url = f"{base_url}/ws/call/{call_sid}"
        ws_url = ws_url.replace("http://", "wss://").replace("https://", "wss://")
        
        # Responder con TwiML que inicia el stream
        # <Start><Stream> inicia un stream WebSocket unidireccional de audio del IVR
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream name="ivr_stream" url="{ws_url}" track="inbound_track"/>
    </Start>
    <Pause length="60"/>
</Response>
"""
        
        logger.debug(f"Sending TwiML: {twiml}")
        return Response(content=twiml, media_type="application/xml")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Twilio webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
