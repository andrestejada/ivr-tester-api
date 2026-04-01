"""WebSocket endpoint para eventos de ejecución en tiempo real."""

import asyncio
import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from src.application.dtos.realtime_events import ExecutionEvent
from src.infrastructure.auth.jwt_verifier import verify_supabase_token
from src.infrastructure.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
)
from src.infrastructure.execution_event_hub import get_execution_event_hub

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/executions/{execution_id}")
async def execution_event_stream_websocket(
    websocket: WebSocket,
    execution_id: UUID,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """
    WebSocket endpoint para recibir eventos de una ejecución en tiempo real.
    
    Requiere autenticación JWT válido.
    
    Eventos: execution_started, status_changed, transcript_partial, transcript_final,
             step_started, step_matched, step_failed, step_logged, execution_finished, execution_error
    
    Args:
        websocket: Conexión WebSocket
        execution_id: ID de la ejecución a monitorear
        token: Token JWT (desde query param, ya que WebSocket no soporta Authorization header)
    """
    hub = get_execution_event_hub()
    user_id = None
    queue = None

    try:
        # 1. Validar y extraer token JWT
        if not token:
            logger.warning(f"WebSocket {execution_id}: No token provided")
            return

        try:
            user_info = verify_supabase_token(token)
            user_id = user_info.get("id")
            logger.debug(f"WebSocket {execution_id}: Usuario autenticado {user_id}")
        except (ExpiredTokenError, InvalidTokenError) as e:
            logger.warning(f"WebSocket {execution_id}: Token inválido: {e}")
            return

        # 2. Aceptar conexión y suscribirse
        await websocket.accept()
        logger.info(f"WebSocket {execution_id}: Conexión aceptada para usuario {user_id}")

        queue = await hub.subscribe(execution_id)

        # 4. Loop de envío de eventos
        while True:
            # Esperar evento del hub (con timeout de reconexión)
            event: ExecutionEvent = await asyncio.wait_for(
                queue.get(),
                timeout=300.0,  # 5 minutos de timeout
            )

            # Serializar y enviar
            event_dict = event.to_dict()
            await websocket.send_json(event_dict)
            logger.debug(f"WebSocket {execution_id}: Evento {event.event_type.value} enviado")

    except asyncio.TimeoutError:
        logger.info(f"WebSocket {execution_id}: Timeout de inactividad")
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="Timeout de inactividad")

    except WebSocketDisconnect:
        logger.info(f"WebSocket {execution_id}: Cliente desconectado")

    except Exception as e:
        logger.error(f"WebSocket {execution_id}: Error no esperado: {e}", exc_info=True)
        try:
            await websocket.close(code=status.WS_1011_SERVER_ERROR, reason="Error interno")
        except Exception:
            pass

    finally:
        # Limpiar suscripción
        if queue is not None:
            await hub.unsubscribe(execution_id, queue)
            logger.debug(f"WebSocket {execution_id}: Desuscripción completada")
