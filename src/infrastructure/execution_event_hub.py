"""Hub de eventos realtime para ejecuciones.

Gestiona suscriptores por execution_id, permite publicar eventos
y realiza cleanup de conexiones caídas.
"""

import asyncio
import logging
from typing import Callable, Optional
from uuid import UUID

from src.application.dtos.realtime_events import ExecutionEvent

logger = logging.getLogger(__name__)


class ExecutionEventHub:
    """Hub central para distribución de eventos en tiempo real por ejecución.
    
    Mantiene un registro de suscriptores agrupados por execution_id.
    Permite publicار eventos que se envían a todos los suscriptores de esa ejecución.
    Limpia automáticamente conexiones muertas al detectarlas.
    """

    def __init__(self):
        """Inicializa el hub."""
        # Dict[execution_id → Set[asyncio.Queue]]
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, execution_id: UUID) -> asyncio.Queue:
        """Suscribe un nuevo cliente a una ejecución.
        
        Args:
            execution_id: ID de la ejecución a monitorear
            
        Returns:
            asyncio.Queue que recibirá eventos de esa ejecución
        """
        execution_id_str = str(execution_id)
        queue = asyncio.Queue()

        async with self._lock:
            if execution_id_str not in self._subscribers:
                self._subscribers[execution_id_str] = set()
            self._subscribers[execution_id_str].add(queue)

        logger.debug(f"Subscriber agregado a ejecución {execution_id_str}")
        return queue

    async def unsubscribe(self, execution_id: UUID, queue: asyncio.Queue) -> None:
        """Desuscribe un cliente de una ejecución.
        
        Args:
            execution_id: ID de la ejecución
            queue: Queue a remover
        """
        execution_id_str = str(execution_id)

        async with self._lock:
            if execution_id_str in self._subscribers:
                self._subscribers[execution_id_str].discard(queue)
                if not self._subscribers[execution_id_str]:
                    del self._subscribers[execution_id_str]
                    logger.debug(f"Grupo de ejecución {execution_id_str} limpiado (sin suscriptores)")

        logger.debug(f"Subscriber removido de ejecución {execution_id_str}")

    async def publish(self, event: ExecutionEvent) -> None:
        """Publica un evento a todos los suscriptores (no bloqueante).
        
        Si algún suscriptor tiene su queue llena/muerta, intenta descartarlo
        para evitar acumular basura.
        
        Args:
            event: Evento a publicar
        """
        execution_id_str = str(event.execution_id)

        async with self._lock:
            subscribers = self._subscribers.get(execution_id_str)
            if not subscribers:
                logger.debug(f"Sin suscriptores para evento {event.event_type.value} en {execution_id_str}")
                return
            
            # Copiar el set para poder iterar sin lock
            subscribers_copy = subscribers.copy()

        # Enviar a todos (fuera del lock)
        dead_queues = []
        for queue in subscribers_copy:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Queue llena para ejecución {execution_id_str}, marcando para limpieza")
                dead_queues.append(queue)
            except Exception as e:
                logger.error(f"Error enviando evento a queue: {e}")
                dead_queues.append(queue)

        # Limpiar queues muertas
        if dead_queues:
            async with self._lock:
                for queue in dead_queues:
                    self._subscribers.get(execution_id_str, set()).discard(queue)

        logger.debug(
            f"Evento {event.event_type.value} publicado a {len(subscribers_copy)} suscriptores en {execution_id_str}"
        )

    async def close_execution(self, execution_id: UUID) -> None:
        """Cierra todos los suscriptores de una ejecución (llamado al terminar).
        
        Opcionalmente envía evento terminal antes de limpiar.
        
        Args:
            execution_id: ID de la ejecución
        """
        execution_id_str = str(execution_id)

        async with self._lock:
            if execution_id_str in self._subscribers:
                subscribers = self._subscribers.pop(execution_id_str)
                logger.info(f"Cerrando {len(subscribers)} suscriptores de ejecución {execution_id_str}")

    async def cleanup_all(self) -> None:
        """Limpia todas las suscripciones (para testing, shutdown, etc)."""
        async with self._lock:
            count = sum(len(subs) for subs in self._subscribers.values())
            self._subscribers.clear()
            logger.info(f"Cleanup: {count} suscriptores removidos")


# Singleton global
_execution_event_hub: Optional[ExecutionEventHub] = None


def get_execution_event_hub() -> ExecutionEventHub:
    """Obtiene o crea el singleton ExecutionEventHub.
    
    Returns:
        Instancia global de ExecutionEventHub
    """
    global _execution_event_hub
    if _execution_event_hub is None:
        _execution_event_hub = ExecutionEventHub()
    return _execution_event_hub
