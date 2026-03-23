"""Thread-safe store for active call sessions and their audio queues."""

import asyncio
from typing import Optional
import logging

from src.domain.entities.call_session import CallSessionEntity

logger = logging.getLogger(__name__)


class CallSessionStore:
    """
    Almacén sincronizado de sesiones activas de llamadas.
    
    Mantiene un mapa de call_sid → CallSessionEntity + asyncio.Queue para audio.
    Permite que el WebSocket enqueue audio y que el orquestador lo dequeue.
    """

    def __init__(self) -> None:
        """Inicializa el store."""
        self._sessions: dict[str, CallSessionEntity] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, call_sid: str) -> CallSessionEntity:
        """Crea una nueva sesión de llamada.
        
        Args:
            call_sid: ID único de la llamada asignado por proveedor
            
        Returns:
            CallSessionEntity creada
        """
        async with self._lock:
            if call_sid in self._sessions:
                logger.warning(f"Session {call_sid} ya existe, recreando...")
            
            session = CallSessionEntity(call_sid=call_sid)
            queue: asyncio.Queue = asyncio.Queue()
            
            self._sessions[call_sid] = session
            self._queues[call_sid] = queue
            
            logger.debug(f"Session {call_sid} created")
            return session

    async def get_session(self, call_sid: str) -> Optional[CallSessionEntity]:
        """Obtiene una sesión activa.
        
        Args:
            call_sid: ID de la llamada
            
        Returns:
            CallSessionEntity si existe, None si no
        """
        async with self._lock:
            return self._sessions.get(call_sid)

    async def is_session_active(self, call_sid: str) -> bool:
        """Verifica si una sesión está activa.
        
        Args:
            call_sid: ID de la llamada
            
        Returns:
            True si la sesión existe y está activa
        """
        async with self._lock:
            session = self._sessions.get(call_sid)
            return session.is_active if session else False

    async def enqueue_audio(self, call_sid: str, audio_bytes: bytes) -> bool:
        """Encola audio recibido por WebSocket.
        
        Args:
            call_sid: ID de la llamada
            audio_bytes: Buffer de audio en formato mulaw
            
        Returns:
            True si se encoló exitosamente, False si sesión no existe
        """
        async with self._lock:
            queue = self._queues.get(call_sid)
            if not queue:
                logger.warning(f"Queue not found for call_sid: {call_sid}")
                return False
        
        # Enqueue fuera del lock para no bloquear
        await queue.put(audio_bytes)
        return True

    async def clear_queue(self, call_sid: str) -> None:
        """Limpia la cola de audio descartando los chunks pendientes."""
        async with self._lock:
            queue = self._queues.get(call_sid)
            if not queue:
                return
            
            # Vaciar la cola completamente
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def dequeue_audio(
        self, call_sid: str, timeout_seconds: float = 10.0
    ) -> bytes:
        """Dequeue audio para procesar.
        
        Args:
            call_sid: ID de la llamada
            timeout_seconds: Timeout para esperar audio
            
        Returns:
            Buffer de audio dequeued
            
        Raises:
            TimeoutError si no hay audio en el timeout
            ValueError si la sesión no existe
        """
        async with self._lock:
            queue = self._queues.get(call_sid)
            if not queue:
                raise ValueError(f"No queue for call_sid: {call_sid}")
        
        try:
            audio = await asyncio.wait_for(
                queue.get(), timeout=timeout_seconds
            )
            return audio
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"No audio received for call_sid {call_sid} within {timeout_seconds}s"
            )

    async def try_dequeue_audio(
        self, call_sid: str, timeout_seconds: float = 1.0
    ) -> Optional[bytes]:
        """Intenta dequeue de audio con timeout corto.
        
        Args:
            call_sid: ID de la llamada
            timeout_seconds: Timeout corto para esperar audio
            
        Returns:
            Buffer de audio si hay datos, None si hubo timeout
            
        Raises:
            ValueError si la sesión no existe
        """
        async with self._lock:
            queue = self._queues.get(call_sid)
            if not queue:
                raise ValueError(f"No queue for call_sid: {call_sid}")

        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None

    async def close_session(self, call_sid: str) -> None:
        """Cierra y limpia una sesión.
        
        Args:
            call_sid: ID de la llamada
        """
        async with self._lock:
            if call_sid in self._sessions:
                session = self._sessions[call_sid]
                session.is_active = False
                logger.debug(f"Session {call_sid} closed")
            
            # Limpiar queue y session
            self._sessions.pop(call_sid, None)
            self._queues.pop(call_sid, None)

    async def cleanup_all(self) -> None:
        """Limpia todas las sesiones (para testing, shutdown, etc)."""
        async with self._lock:
            self._sessions.clear()
            self._queues.clear()
            logger.debug("All sessions cleaned up")


# Singleton global
_call_session_store: Optional[CallSessionStore] = None


def get_call_session_store() -> CallSessionStore:
    """Obtiene o crea el singleton CallSessionStore.
    
    Returns:
        Instancia global de CallSessionStore
    """
    global _call_session_store
    if _call_session_store is None:
        _call_session_store = CallSessionStore()
    return _call_session_store
