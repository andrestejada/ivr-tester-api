"""Unit tests para ExecutionEventHub de realtime events."""

import pytest
import asyncio
from uuid import uuid4

from src.application.dtos.realtime_events import (
    ExecutionEvent,
    ExecutionEventType,
)
from src.infrastructure.execution_event_hub import ExecutionEventHub


@pytest.mark.asyncio
class TestExecutionEventHub:
    """Tests para ExecutionEventHub."""

    async def test_subscribe_creates_queue(self):
        """Test: subscribe retorna una queue para recibir eventos."""
        hub = ExecutionEventHub()
        execution_id = uuid4()

        queue = await hub.subscribe(execution_id)

        assert queue is not None
        assert isinstance(queue, asyncio.Queue)

    async def test_publish_to_subscribers(self):
        """Test: publish envía evento a todos los suscriptores."""
        hub = ExecutionEventHub()
        execution_id = uuid4()

        # 2 suscriptores a la misma ejecución
        queue1 = await hub.subscribe(execution_id)
        queue2 = await hub.subscribe(execution_id)

        # Publicar un evento
        event = ExecutionEvent.execution_started(execution_id)
        await hub.publish(event)

        # Ambas queues deben recibir el evento
        received1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        received2 = await asyncio.wait_for(queue2.get(), timeout=1.0)

        assert received1.event_type == ExecutionEventType.EXECUTION_STARTED
        assert received2.event_type == ExecutionEventType.EXECUTION_STARTED

    async def test_unsubscribe_removes_queue(self):
        """Test: unsubscribe remueve la queue y no recibe más eventos."""
        hub = ExecutionEventHub()
        execution_id = uuid4()

        queue = await hub.subscribe(execution_id)
        await hub.unsubscribe(execution_id, queue)

        # Publicar evento
        event = ExecutionEvent.execution_finished(execution_id, "PASSED", 60)
        await hub.publish(event)

        # La queue no debería recibir nada
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    async def test_multiple_executions_isolated(self):
        """Test: eventos de diferentes ejecuciones están aislados."""
        hub = ExecutionEventHub()
        exec_id1 = uuid4()
        exec_id2 = uuid4()

        queue1 = await hub.subscribe(exec_id1)
        queue2 = await hub.subscribe(exec_id2)

        # Publicar a ejecución 1
        event1 = ExecutionEvent.execution_started(exec_id1)
        await hub.publish(event1)

        # queue1 debe recibir
        received1 = await asyncio.wait_for(queue1.get(), timeout=0.5)
        assert received1.execution_id == exec_id1

        # queue2 no debe tener nada
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue2.get(), timeout=0.1)

    async def test_close_execution_cleanup(self):
        """Test: close_execution limpia suscriptores de esa ejecución."""
        hub = ExecutionEventHub()
        execution_id = uuid4()

        queue = await hub.subscribe(execution_id)
        await hub.close_execution(execution_id)

        # Publicar evento
        event = ExecutionEvent.execution_finished(execution_id, "PASSED", 60)
        await hub.publish(event)

        # No se debe recibir nada (la ejecución se cerró)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    async def test_event_serialization(self):
        """Test: ExecutionEvent serializa correctamente a dict."""
        execution_id = uuid4()

        event = ExecutionEvent.execution_started(execution_id)
        event_dict = event.to_dict()

        assert event_dict["event_type"] == "execution_started"
        assert event_dict["execution_id"] == str(execution_id)
        assert event_dict["schema_version"] == "v1"
        assert "timestamp" in event_dict
        assert "data" in event_dict

    async def test_cleanup_all(self):
        """Test: cleanup_all limpia todas las suscripciones."""
        hub = ExecutionEventHub()
        exec_id1 = uuid4()
        exec_id2 = uuid4()

        queue1 = await hub.subscribe(exec_id1)
        queue2 = await hub.subscribe(exec_id2)

        await hub.cleanup_all()

        # Publicar eventos
        event1 = ExecutionEvent.execution_finished(exec_id1, "PASSED", 60)
        event2 = ExecutionEvent.execution_finished(exec_id2, "FAILED", 40)

        await hub.publish(event1)
        await hub.publish(event2)

        # Ninguna queue debe recibir
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue1.get(), timeout=0.1)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue2.get(), timeout=0.1)
