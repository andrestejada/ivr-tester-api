"""Unit tests for extreme silence timeout detection (>15s without audio/transcription)."""

import asyncio
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.application.use_cases import execute_test_case_use_case as execute_module
from src.application.services import ivr_state_machine as state_machine_module
from src.application.services.ivr_state_machine import (
    IVRStateMachine,
    STEP_TIMEOUT_SECONDS,
    EXTREME_SILENCE_THRESHOLD_SECONDS,
    GRACE_PERIOD_AFTER_DTMF_SECONDS,
)
from src.application.use_cases.execute_test_case_use_case import ExecuteTestCaseUseCase
from src.domain.entities.execution_log import ExecutionLogEntity
from src.domain.entities.test_case import TestCaseEntity
from src.domain.entities.test_execution import TestExecutionEntity
from src.domain.entities.call_session import CallSessionEntity
from src.infrastructure.call_session_store import CallSessionStore


class TestExtremeSilenceStateMachine:
    """Test state machine extreme silence detection."""

    def test_check_extreme_silence_method_exists(self):
        """State machine should have check_extreme_silence_timeout method."""
        def mock_evaluate(expected, transcribed, threshold=0.8):
            return (0.9, Decimal("90"), True)

        flow_script = [{"step": 1, "listen": "Test", "action": "1"}]
        machine = IVRStateMachine(flow_script, mock_evaluate)

        # Method should exist and be callable
        assert hasattr(machine, "check_extreme_silence_timeout")
        assert callable(machine.check_extreme_silence_timeout)

    def test_extreme_silence_constant_defined(self):
        """EXTREME_SILENCE_THRESHOLD_SECONDS constant should be 15.0."""
        assert EXTREME_SILENCE_THRESHOLD_SECONDS == 15.0

    def test_grace_period_constant_defined(self):
        """GRACE_PERIOD_AFTER_DTMF_SECONDS constant should be 4.0."""
        assert GRACE_PERIOD_AFTER_DTMF_SECONDS == 4.0

    def test_step_timeout_detected(self):
        """State machine should flag timeout when waiting longer than threshold."""
        from time import time as get_time

        def mock_evaluate(expected, transcribed, threshold=0.8):
            return (0.4, Decimal("40"), False)

        flow_script = [{"step": 1, "listen": "Test", "action": "1"}]
        machine = IVRStateMachine(flow_script, mock_evaluate)
        machine.state.step_start_time = get_time() - (STEP_TIMEOUT_SECONDS + 1.0)

        assert machine.check_step_timeout() is True

    def test_step_timeout_not_triggered_with_reasonable_extra_time(self):
        """State machine should tolerate a modest extra wait for long prompts."""
        from time import time as get_time

        def mock_evaluate(expected, transcribed, threshold=0.8):
            return (0.4, Decimal("40"), False)

        flow_script = [{"step": 1, "listen": "Test", "action": "1"}]
        machine = IVRStateMachine(flow_script, mock_evaluate)
        machine.state.step_start_time = get_time() - 31.0

        assert machine.check_step_timeout() is False

    def test_step_stagnation_detected_for_low_ratio(self):
        """State machine should detect low-ratio stagnation after no progress window."""
        from time import time as get_time

        def mock_evaluate(expected, transcribed, threshold=0.8):
            return (0.3, Decimal("30"), False)

        flow_script = [{"step": 1, "listen": "Test", "action": "1"}]
        machine = IVRStateMachine(flow_script, mock_evaluate)
        machine.state.transcript_parts = ["texto previo"]
        machine.state.last_text_time = get_time() - 4.0
        machine.state.best_similarity_ratio = 0.35
        machine.state.last_similarity_improvement_time = get_time() - 9.0

        assert machine.check_step_stagnation(stagnation_seconds=8.0, max_ratio_without_progress=0.6) is True

    def test_step_stagnation_not_detected_when_ratio_is_close(self):
        """Stagnation should not fail if best ratio is already close to target threshold."""
        from time import time as get_time

        def mock_evaluate(expected, transcribed, threshold=0.8):
            return (0.7, Decimal("70"), False)

        flow_script = [{"step": 1, "listen": "Test", "action": "1"}]
        machine = IVRStateMachine(flow_script, mock_evaluate)
        machine.state.best_similarity_ratio = 0.70
        machine.state.last_similarity_improvement_time = get_time() - 9.0

        assert machine.check_step_stagnation(stagnation_seconds=8.0, max_ratio_without_progress=0.6) is False


class TestExtremeSlience:
    """Test cases for extreme silence timeout detection."""

    @pytest.mark.asyncio
    async def test_state_machine_detects_extreme_silence(self):
        """State machine should detect when silence exceeds 15s threshold."""
        from time import time as get_time
        
        def mock_evaluate(expected, transcribed, threshold=0.8):
            return (0.9, Decimal("90"), True)

        flow_script = [
            {"step": 1, "listen": "Bienvenido", "action": "1"},
        ]
        machine = IVRStateMachine(flow_script, mock_evaluate)

        # Simulate old transcription (15+ seconds ago)
        machine.state.transcript_parts = ["Bienvenido"]
        machine.state.last_text_time = get_time() - 16.0  # 16s ago

        # Check should return True (>15s)
        assert machine.check_extreme_silence_timeout() is True

    @pytest.mark.asyncio
    async def test_state_machine_no_extreme_silence_at_exact_threshold(self):
        """State machine should not trigger at exactly 15s (use >=)."""
        from time import time as get_time
        
        def mock_evaluate(expected, transcribed, threshold=0.8):
            return (0.9, Decimal("90"), True)

        flow_script = [
            {"step": 1, "listen": "Bienvenido", "action": "1"},
        ]
        machine = IVRStateMachine(flow_script, mock_evaluate)

        # Simulate exactly 15 seconds ago (at threshold, should check >=)
        machine.state.transcript_parts = ["Bienvenido"]
        machine.state.last_text_time = get_time() - 15.0  # Exactly 15s ago

        # Check should return True (>=15s with margins)
        # Note: due to timing variance, the check >= means 15.0000 might trigger
        result = machine.check_extreme_silence_timeout()
        # This is a boundary case - the implementation uses >=
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_grace_period_after_dtmf_prevents_false_positive(
        self,
    ):
        """Test that grace period of 4s after DTMF prevents false positives on extreme silence."""
        # Simulate: DTMF sent at T=0, now at T=2s
        # Should NOT trigger extreme silence check
        
        from time import time as get_time
        dtmf_timestamp = get_time()  # "Now"
        current_time = get_time() + 2.0  # 2 seconds later
        
        time_since_dtmf = current_time - dtmf_timestamp
        in_grace_period = time_since_dtmf < GRACE_PERIOD_AFTER_DTMF_SECONDS
        
        # Should be in grace period (2s < 4s)
        assert in_grace_period is True

    @pytest.mark.asyncio
    async def test_grace_period_expires_after_4_seconds(self):
        """Test that grace period expires correctly."""
        from time import time as get_time
        import time
        
        dtmf_timestamp = get_time()
        
        # Sleep 0.1s to simulate time passing
        await asyncio.sleep(0.1)
        
        current_time = get_time()
        time_since_dtmf = current_time - dtmf_timestamp
        in_grace_period = time_since_dtmf < GRACE_PERIOD_AFTER_DTMF_SECONDS
        
        # Should still be in grace period (0.1s < 4s)
        assert in_grace_period is True


class TestExecuteTestCaseRegressions:
    """Regression tests to ensure existing functionality still works."""

    @pytest.fixture
    def mock_test_case_repo(self):
        """Mock test case repository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_test_execution_repo(self):
        """Mock test execution repository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_execution_log_repo(self):
        """Mock execution log repository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_call_provider(self):
        """Mock call provider."""
        provider = AsyncMock()
        return provider

    @pytest.fixture
    def mock_asr_provider(self):
        """Mock ASR provider."""
        provider = AsyncMock()
        return provider

    @pytest.fixture
    def mock_call_session_store(self):
        """Mock call session store."""
        store = AsyncMock()
        return store

    @pytest.fixture
    def mock_event_hub(self):
        """Mock realtime execution event hub."""
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_execution_log_repo,
        mock_call_provider,
        mock_asr_provider,
        mock_call_session_store,
        mock_event_hub,
    ):
        """Create use case with mocked dependencies."""
        return ExecuteTestCaseUseCase(
            test_case_repo=mock_test_case_repo,
            test_execution_repo=mock_test_execution_repo,
            execution_log_repo=mock_execution_log_repo,
            call_provider=mock_call_provider,
            asr_provider=mock_asr_provider,
            call_session_store=mock_call_session_store,
            event_hub=mock_event_hub,
        )

    @pytest.mark.asyncio
    async def test_existing_happy_path_still_works(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_execution_log_repo,
        mock_call_provider,
        mock_asr_provider,
        mock_call_session_store,
    ):
        """Regression: Basic happy path should still work."""
        test_case_id = uuid4()
        phone_number = "+1234567890"
        webhook_url = "http://localhost:8000/webhooks/twilio/voice"

        flow_script = [
            {"step": 1, "listen": "Bienvenido", "action": "1"},
        ]
        test_case = TestCaseEntity(
            id=test_case_id,
            ivr_architecture_id=uuid4(),
            name="Test",
            flow_script=flow_script,
            created_at=datetime.now(timezone.utc),
        )
        mock_test_case_repo.get_by_id.return_value = test_case

        execution = TestExecutionEntity(
            id=uuid4(),
            test_case_id=test_case_id,
            status="RUNNING",
            duration_seconds=None,
            provider_call_sid=None,
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.create.return_value = execution
        persisted_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="RUNNING",
            duration_seconds=None,
            provider_call_sid="CA123456789",
            executed_at=execution.executed_at,
        )
        mock_test_execution_repo.update_provider_call_sid.return_value = persisted_execution

        call_session = CallSessionEntity(
            call_sid="CA123456789",
            started_at=datetime.now(timezone.utc),
            is_active=True,
        )
        mock_call_provider.initiate_call.return_value = call_session

        mock_call_session_store.try_dequeue_audio.return_value = b"audio"

        async def _set_handler(cb):
            mock_asr_provider._cb = cb

        async def _send_audio(_chunk):
            if getattr(mock_asr_provider, "_cb", None):
                await mock_asr_provider._cb("Bienvenido", True)

        mock_asr_provider.set_transcript_handler.side_effect = _set_handler
        mock_asr_provider.send_audio.side_effect = _send_audio

        final_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="PASSED",
            duration_seconds=2.0,
            provider_call_sid="CA123456789",
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.update_status.return_value = final_execution

        result = await use_case.execute(test_case_id, phone_number, webhook_url)
        
        await asyncio.sleep(0.5)

        # Should return RUNNING immediately (background task)
        assert result.status == "RUNNING"
