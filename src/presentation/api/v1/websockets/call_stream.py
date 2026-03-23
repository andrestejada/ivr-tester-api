"""WebSocket endpoint for Twilio Media Streams."""

import json
import base64
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.call_session_store import get_call_session_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/call/{call_sid}")
async def call_stream_websocket(websocket: WebSocket, call_sid: str) -> None:
    """
    WebSocket endpoint para recibir audio stream de Twilio.
    
    Twilio envía audio en eventos JSON:
    {
        "event": "start" | "media" | "stop" | "connected",
        "sequenceNumber": int,
        "media": { "payload": "<base64-mulaw-audio>" },  # solo en "media"
        "streamSid": str
    }
    
    Este handler:
    - Recibe eventos JSON
    - Decodifica el payload base64 (mulaw 8kHz)
    - Encola el audio en CallSessionStore
    
    Args:
        websocket: Conexión WebSocket
        call_sid: ID de la llamada
    """
    
    store = get_call_session_store()
    
    # Verificar que la sesión existe
    session = await store.get_session(call_sid)
    if not session:
        logger.warning(f"WebSocket: No session for call_sid {call_sid}, aborting")
        await websocket.close(code=1008, reason="No session found")
        return
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket connected for call {call_sid}")
        
        while True:
            # Recibir mensaje JSON de Twilio
            data = await websocket.receive_text()
            message = json.loads(data)
            
            event = message.get("event", "unknown")
            
            # Solo registrar eventos que no sean "media" para no saturar los logs
            if event != "media":
                logger.debug(f"WebSocket event: {event} for call {call_sid}")
            
            # Manejar eventos
            if event == "start":
                logger.info(f"Stream started for call {call_sid}")
            
            elif event == "connected":
                logger.info(f"Stream connected for call {call_sid}")
            
            elif event == "media":
                # Extraer y decodificar audio
                try:
                    payload_b64 = message.get("media", {}).get("payload", "")
                    if payload_b64:
                        audio_bytes = base64.b64decode(payload_b64)
                        # Encolar audio silenciosamente
                        enqueued = await store.enqueue_audio(call_sid, audio_bytes)
                        if not enqueued:
                            logger.warning(
                                f"Failed to enqueue audio for {call_sid}"
                            )
                except Exception as e:
                    logger.error(f"Error processing audio: {e}")
            
            elif event == "stop":
                logger.info(f"Stream stopped for call {call_sid}")
                # Cerrar sesión
                await store.close_session(call_sid)
                break
            
            else:
                logger.debug(f"Unknown event: {event}")
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
        await store.close_session(call_sid)
    
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}", exc_info=True)
        await store.close_session(call_sid)
    
    finally:
        # Asegurar que la sesión se cierra
        await store.close_session(call_sid)
