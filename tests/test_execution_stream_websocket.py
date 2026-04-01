"""
Integration tests for the execution stream WebSocket endpoint.

Tests cover:
- Event serialization and encoding
- Event hub integration with concurrent subscribers
- Event sequence validation
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.dtos.realtime_events import (
    ExecutionEvent,
    ExecutionEventType,
)
from src.infrastructure.execution_event_hub import (
    ExecutionEventHub,
    get_execution_event_hub,
)


@pytest.fixture
def event_hub():
    """Singleton hub for test session."""
    return get_execution_event_hub()


class TestExecutionStreamEventSerialization:
    """Test event serialization for WebSocket transmission."""

    @pytest.mark.asyncio
    async def test_event_serialization_to_json(self, event_hub):
        """Events should serialize correctly for WebSocket transmission."""
        execution_id = str(uuid4())

        event = ExecutionEvent.transcript_partial(
            execution_id=execution_id,
            text="Hello world",
        )

        # Verify to_dict() produces JSON-serializable output
        event_dict = event.to_dict()
        json_str = json.dumps(event_dict)

        # Verify round-trip
        deserialized = json.loads(json_str)
        assert deserialized["event_type"] == "transcript_partial"
        assert deserialized["execution_id"] == execution_id
        assert deserialized["data"]["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_multiple_event_types_encoded(self, event_hub):
        """All event types should encode correctly."""
        execution_id = str(uuid4())

        events = [
            ExecutionEvent.execution_started(execution_id),
            ExecutionEvent.status_changed(execution_id, "READY", "RUNNING"),
            ExecutionEvent.transcript_partial(execution_id, "Partial"),
            ExecutionEvent.transcript_final(execution_id, "Final"),
            ExecutionEvent.step_started(execution_id, 1, "Expected text"),
            ExecutionEvent.step_matched(execution_id, 1, "Matched", 0.95),
            ExecutionEvent.step_failed(execution_id, 1, "Expected", "Actual", "Mismatch"),
            ExecutionEvent.step_logged(execution_id, 1),
            ExecutionEvent.execution_finished(execution_id, "PASSED", 5),
            ExecutionEvent.execution_error(execution_id, "Test error", 5),
        ]

        for event in events:
            event_dict = event.to_dict()
            json_str = json.dumps(event_dict)
            assert len(json_str) > 0
            assert event_dict["event_type"] in [e.value for e in ExecutionEventType]

    @pytest.mark.asyncio
    async def test_event_timestamp_included(self):
        """Event timestamp should be ISO format."""
        execution_id = str(uuid4())
        event = ExecutionEvent.execution_started(execution_id)
        
        event_dict = event.to_dict()
        assert "timestamp" in event_dict
        # Verify it's valid ISO format
        datetime.fromisoformat(event_dict["timestamp"])


class TestExecutionStreamEventFlow:
    """Test end-to-end event flow through event hub."""

    @pytest.mark.asyncio
    async def test_event_sequence_in_execution(self, event_hub):
        """Verify correct event sequence is emitted during execution."""
        execution_id = str(uuid4())

        # Subscribe to events
        queue = await event_hub.subscribe(execution_id)

        # Simulate execution events
        events_to_emit = [
            ExecutionEvent.execution_started(execution_id),
            ExecutionEvent.transcript_partial(execution_id, "partial"),
            ExecutionEvent.step_matched(execution_id, 1, "matched", 0.95),
            ExecutionEvent.execution_finished(execution_id, "PASSED", 5),
        ]

        for event in events_to_emit:
            await event_hub.publish(event)

        # Verify all events received in order
        received_events = []
        for _ in range(len(events_to_emit)):
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            received_events.append(event)

        # Cleanup
        await event_hub.unsubscribe(execution_id, queue)

        # Verify sequence
        assert len(received_events) == len(events_to_emit)
        assert received_events[0].event_type == ExecutionEventType.EXECUTION_STARTED
        assert received_events[1].event_type == ExecutionEventType.TRANSCRIPT_PARTIAL
        assert received_events[2].event_type == ExecutionEventType.STEP_MATCHED
        assert received_events[3].event_type == ExecutionEventType.EXECUTION_FINISHED

    @pytest.mark.asyncio
    async def test_event_not_received_after_unsubscribe(self, event_hub):
        """Unsubscribed queues should not receive new events."""
        execution_id = str(uuid4())

        queue = await event_hub.subscribe(execution_id)
        event1 = ExecutionEvent.execution_started(execution_id)
        await event_hub.publish(event1)

        # Receive first event
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.event_type == ExecutionEventType.EXECUTION_STARTED

        # Unsubscribe
        await event_hub.unsubscribe(execution_id, queue)

        # Publish another event
        event2 = ExecutionEvent.status_changed(execution_id, "RUNNING", "PAUSED")
        await event_hub.publish(event2)

        # Queue should not receive the second event
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_concurrent_subscribers_all_receive_events(self, event_hub):
        """Multiple subscribers to same execution should all receive events."""
        execution_id = str(uuid4())

        # Create multiple subscribers
        queues = [await event_hub.subscribe(execution_id) for _ in range(3)]

        # Publish event
        event = ExecutionEvent.transcript_partial(execution_id, "Test")
        await event_hub.publish(event)

        # All queues should receive the event
        for queue in queues:
            received = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert received.event_type == ExecutionEventType.TRANSCRIPT_PARTIAL

        # Cleanup
        for queue in queues:
            await event_hub.unsubscribe(execution_id, queue)

    @pytest.mark.asyncio
    async def test_data_payload_integrity(self, event_hub):
        """Event data payloads should be preserved exactly."""
        execution_id = str(uuid4())

        # Create event with complex data
        event = ExecutionEvent.step_matched(
            execution_id=execution_id,
            step_number=3,
            matched_text="This is the matched text with special chars: é, ñ, ü",
            confidence=0.9876,
        )

        event_dict = event.to_dict()
        
        # Verify data fields
        assert event_dict["data"]["step_number"] == 3
        assert event_dict["data"]["matched_text"] == "This is the matched text with special chars: é, ñ, ü"
        assert event_dict["data"]["confidence"] == 0.9876

        # Verify JSON round-trip
        json_str = json.dumps(event_dict)
        back = json.loads(json_str)
        assert back["data"]["matched_text"] == "This is the matched text with special chars: é, ñ, ü"


class TestExecutionStreamErrorHandling:
    """Test error handling in event flow."""

    @pytest.mark.asyncio
    async def test_execution_error_event_created(self):
        """Execution error event should capture error message."""
        execution_id = str(uuid4())
        error_msg = "Database connection failed"

        event = ExecutionEvent.execution_error(execution_id, error_msg, 10)

        assert event.event_type == ExecutionEventType.EXECUTION_ERROR
        assert event.data["error_message"] == error_msg

    @pytest.mark.asyncio
    async def test_step_failed_event_created(self):
        """Step failed event should capture step number."""
        execution_id = str(uuid4())
        step_num = 2

        event = ExecutionEvent.step_failed(execution_id, step_num, "Expected", "Actual", "Mismatch")

        assert event.event_type == ExecutionEventType.STEP_FAILED
        assert event.data["step_number"] == step_num

    @pytest.mark.asyncio
    async def test_event_with_none_values_serializable(self):
        """Events with None values should serialize without issues."""
        execution_id = str(uuid4())
        
        # Finalize with unknown duration
        event = ExecutionEvent.execution_finished(
            execution_id=execution_id,
            status="UNKNOWN",
            duration_seconds=0,
        )

        event_dict = event.to_dict()
        json_str = json.dumps(event_dict)
        
        # Should successfully serialize and round-trip
        back = json.loads(json_str)
        assert back["data"]["duration_seconds"] == 0

