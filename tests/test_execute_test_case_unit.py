"""Unit tests for ExecuteTestCaseUseCase."""

import asyncio
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.application.use_cases import execute_test_case_use_case as execute_module
from src.application.services import ivr_state_machine as state_machine_module

from src.application.use_cases.execute_test_case_use_case import ExecuteTestCaseUseCase
from src.domain.entities.execution_log import ExecutionLogEntity
from src.domain.entities.test_case import TestCaseEntity
from src.domain.entities.test_execution import TestExecutionEntity
from src.domain.entities.call_session import CallSessionEntity
from src.infrastructure.call_session_store import CallSessionStore


@pytest.fixture
def mock_test_case_repo():
    """Mock test case repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_test_execution_repo():
    """Mock test execution repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_execution_log_repo():
    """Mock execution log repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_call_provider():
    """Mock call provider."""
    provider = AsyncMock()
    return provider


@pytest.fixture
def mock_asr_provider():
    """Mock ASR provider."""
    provider = AsyncMock()
    return provider


@pytest.fixture
def mock_call_session_store():
    """Mock call session store."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_event_hub():
    """Mock realtime execution event hub."""
    return AsyncMock()


@pytest.fixture
def use_case(
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


class TestExecuteTestCaseUseCase:
    """Test cases for ExecuteTestCaseUseCase."""

    @pytest.mark.asyncio
    async def test_execute_happy_path(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_execution_log_repo,
        mock_call_provider,
        mock_asr_provider,
        mock_call_session_store,
    ):
        """Test successful execution with matching transcriptions."""
        # Setup
        test_case_id = uuid4()
        phone_number = "+1234567890"
        webhook_url = "http://localhost:8000/webhooks/twilio/voice"

        # Mock test case
        flow_script = [
            {"step": 1, "listen": "Bienvenido", "action": "1"},
            {"step": 2, "listen": "Gracias", "action": None},
        ]
        test_case = TestCaseEntity(
            id=test_case_id,
            ivr_architecture_id=uuid4(),
            name="Test Case",
            flow_script=flow_script,
            created_at=datetime.now(timezone.utc),
        )
        mock_test_case_repo.get_by_id.return_value = test_case

        # Mock execution creation
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

        # Mock call session returned by initiate_call
        call_session = CallSessionEntity(
            call_sid="CA123456789",
            started_at=datetime.now(timezone.utc),
            is_active=True,
        )
        mock_call_provider.initiate_call.return_value = call_session

        # Mock audio dequeue (simulate audio received)
        mock_call_session_store.try_dequeue_audio.side_effect = [
            b"audio_data_1",  # First step
            b"audio_data_2",  # Second step
        ]

        # Mock streaming transcription callbacks
        transcript_queue = ["Bienvenido", "Gracias"]

        async def _set_handler(cb):
            mock_asr_provider._cb = cb

        async def _send_audio(_chunk):
            if getattr(mock_asr_provider, "_cb", None) and transcript_queue:
                text = transcript_queue.pop(0)
                await mock_asr_provider._cb(text, True)

        mock_asr_provider.set_transcript_handler.side_effect = _set_handler
        mock_asr_provider.send_audio.side_effect = _send_audio

        # Mock execution update
        final_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="PASSED",
            duration_seconds=5.0,
            provider_call_sid="CA123456789",
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.update_status.return_value = final_execution

        # Mock hangup
        mock_call_provider.hangup.return_value = None

        # Execute
        result = await use_case.execute(test_case_id, phone_number, webhook_url)
        
        # Wait for background task to complete
        # The execute() method returns immediately with RUNNING status,
        # but creates a background task to process the call.
        # We need to wait enough time for the async task to process all steps.
        await asyncio.sleep(1.0)

        # Assertions
        # The immediate result has status RUNNING (created synchronously)
        assert result.status == "RUNNING"
        
        # But update_status should have been called with PASSED (from background task)
        # Verify update_status was called with PASSED status
        assert mock_test_execution_repo.update_status.called
        # Get the first call to update_status and check the status argument
        call_args = mock_test_execution_repo.update_status.call_args_list[0]
        assert call_args[1]['status'] == 'PASSED'

        # Verify call initiation
        mock_call_provider.initiate_call.assert_called_once_with(
            phone_number=phone_number,
            webhook_url=webhook_url,
        )
        mock_test_execution_repo.update_provider_call_sid.assert_called_once_with(
            execution.id,
            provider_call_sid="CA123456789",
        )

        # Verify streaming transcript handler was used
        assert mock_asr_provider.set_transcript_handler.called

        # Verify DTMF sent for first step
        mock_call_provider.send_dtmf.assert_called_once_with(
            call_sid="CA123456789",
            digits="1",
        )

        # Verify execution logs created
        assert mock_execution_log_repo.create.call_count == 2

        # Verify hangup
        mock_call_provider.hangup.assert_called_once_with("CA123456789")

    @pytest.mark.asyncio
    async def test_execute_transcription_mismatch(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_execution_log_repo,
        mock_call_provider,
        mock_asr_provider,
        mock_call_session_store,
        monkeypatch,
    ):
        """Test fail-fast behavior: first failed step aborts the rest of the flow."""
        # Setup
        test_case_id = uuid4()
        phone_number = "+1234567890"
        webhook_url = "http://localhost:8000/webhooks/twilio/voice"

        # Mock test case
        flow_script = [
            {"step": 1, "listen": "Bienvenido", "action": "1"},
        ]
        test_case = TestCaseEntity(
            id=test_case_id,
            ivr_architecture_id=uuid4(),
            name="Test Case",
            flow_script=flow_script,
            created_at=datetime.now(timezone.utc),
        )
        mock_test_case_repo.get_by_id.return_value = test_case

        # Mock execution
        execution = TestExecutionEntity(
            id=uuid4(),
            test_case_id=test_case_id,
            status="RUNNING",
            duration_seconds=None,
            provider_call_sid=None,
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.create.return_value = execution
        
        # Mock provider call sid update
        persisted_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="RUNNING",
            duration_seconds=None,
            provider_call_sid="CA123456789",
            executed_at=execution.executed_at,
        )
        mock_test_execution_repo.update_provider_call_sid.return_value = persisted_execution
        
        # Mock call session
        call_session = CallSessionEntity(
            call_sid="CA123456789",
            started_at=datetime.now(timezone.utc),
            is_active=True,
        )
        mock_call_provider.initiate_call.return_value = call_session

        # Reduce timeout for fast test
        monkeypatch.setattr(state_machine_module, "STEP_TIMEOUT_SECONDS", 0.1)

        # Mock audio received with immediate mismatch
        mock_call_session_store.try_dequeue_audio.return_value = b"audio_data"

        # ASR: transcription doesn't match ("Esperado: 1, Recibido: Hola")
        async def _set_handler(cb):
            pass

        mock_asr_provider.set_transcript_handler.side_effect = _set_handler
        mock_asr_provider.send_audio.return_value = None

        # When background task calls update_status, set it to FAILED
        failed_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="FAILED",
            duration_seconds=1.0,
            provider_call_sid="CA123456789",
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.update_status.return_value = failed_execution

        # When background task calls create (for execution log), track it
        log_entry = ExecutionLogEntity(
            id=uuid4(),
            execution_id=execution.id,
            step_number=1,
            expected_text="1",
            actual_transcription=None,
            confidence_score=None,
            action_taken="TIMEOUT",
            created_at=datetime.now(timezone.utc),
        )
        mock_execution_log_repo.create.return_value = log_entry

        # Ejecutar: retorna RUNNING inmediatamente
        result = await use_case.execute(test_case_id, phone_number, webhook_url)
        
        # Assertions on immediate response
        assert result.status == "RUNNING"
        assert result.id == execution.id
        
        # Wait for background flow to fail fast by step-timeout
        await asyncio.sleep(0.3)

        failed_status_updates = [
            call
            for call in mock_test_execution_repo.update_status.call_args_list
            if call.kwargs.get("status") == "FAILED"
        ]
        assert failed_status_updates, "Expected execution to finish as FAILED"

        logged_actions = [
            call.args[0].action_taken
            for call in mock_execution_log_repo.create.call_args_list
            if call.args
        ]
        assert any("timeout" in action.lower() for action in logged_actions)

    @pytest.mark.asyncio
    async def test_execute_fails_on_stagnation_before_timeout(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_execution_log_repo,
        mock_call_provider,
        mock_asr_provider,
        mock_call_session_store,
        monkeypatch,
    ):
        """Test stagnation fail-fast: low similarity without progress should fail the step."""
        test_case_id = uuid4()
        phone_number = "+1234567890"
        webhook_url = "http://localhost:8000/webhooks/twilio/voice"

        flow_script = [{"step": 1, "listen": "conocer estados financieros", "action": "5"}]
        test_case = TestCaseEntity(
            id=test_case_id,
            ivr_architecture_id=uuid4(),
            name="Test Stagnation",
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

        # Keep timeout high so stagnation is the first terminal condition
        monkeypatch.setattr(state_machine_module, "STEP_TIMEOUT_SECONDS", 1.0)
        monkeypatch.setattr(execute_module, "STEP_STAGNATION_SECONDS", 0.05)
        monkeypatch.setattr(execute_module, "STEP_STAGNATION_MAX_RATIO", 0.80)
        monkeypatch.setattr(execute_module, "STEP_STAGNATION_MIN_SILENCE_SECONDS", 0.05)

        mock_call_session_store.try_dequeue_audio.return_value = b"audio_data"

        async def _set_handler(cb):
            mock_asr_provider._cb = cb

        sent_once = {"value": False}

        async def _send_audio(_chunk):
            if getattr(mock_asr_provider, "_cb", None) and not sent_once["value"]:
                sent_once["value"] = True
                await mock_asr_provider._cb("conocer saldo", True)

        mock_asr_provider.set_transcript_handler.side_effect = _set_handler
        mock_asr_provider.send_audio.side_effect = _send_audio

        failed_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="FAILED",
            duration_seconds=1.0,
            provider_call_sid="CA123456789",
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.update_status.return_value = failed_execution

        await use_case.execute(test_case_id, phone_number, webhook_url)
        await asyncio.sleep(0.6)

        failed_status_updates = [
            call
            for call in mock_test_execution_repo.update_status.call_args_list
            if call.kwargs.get("status") == "FAILED"
        ]
        assert failed_status_updates, "Expected execution to finish as FAILED"

        logged_actions = [
            call.args[0].action_taken
            for call in mock_execution_log_repo.create.call_args_list
            if call.args
        ]
        assert any("stagnated" in action.lower() for action in logged_actions)

    @pytest.mark.asyncio
    async def test_execute_audio_timeout(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_execution_log_repo,
        mock_call_provider,
        mock_call_session_store,
        mock_asr_provider,
        monkeypatch,
    ):
        """Test execution returns RUNNING immediately, background task handles timeout."""
        # Setup
        test_case_id = uuid4()
        phone_number = "+1234567890"
        webhook_url = "http://localhost:8000/webhooks/twilio/voice"

        # Mock test case
        flow_script = [{"step": 1, "listen": "Bienvenido", "action": "1"}]
        test_case = TestCaseEntity(
            id=test_case_id,
            ivr_architecture_id=uuid4(),
            name="Test Case",
            flow_script=flow_script,
            created_at=datetime.now(timezone.utc),
        )
        mock_test_case_repo.get_by_id.return_value = test_case

        # Mock execution
        execution = TestExecutionEntity(
            id=uuid4(),
            test_case_id=test_case_id,
            status="RUNNING",
            duration_seconds=None,
            provider_call_sid=None,
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.create.return_value = execution
        
        # Mock provider call sid update
        persisted_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="RUNNING",
            duration_seconds=None,
            provider_call_sid="CA123456789",
            executed_at=execution.executed_at,
        )
        mock_test_execution_repo.update_provider_call_sid.return_value = persisted_execution
        
        # Mock call session
        call_session = CallSessionEntity(
            call_sid="CA123456789",
            started_at=datetime.now(timezone.utc),
            is_active=True,
        )
        mock_call_provider.initiate_call.return_value = call_session

        # Reduce timeout for testing
        monkeypatch.setattr(state_machine_module, "STEP_TIMEOUT_SECONDS", 0.1)

        # Mock no audio received (timeout scenario)
        mock_call_session_store.try_dequeue_audio.return_value = None

        # ASR handler
        async def _set_handler(_cb):
            return None

        mock_asr_provider.set_transcript_handler.side_effect = _set_handler

        # When background task fails, mock the FAILED status update
        failed_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="FAILED",
            duration_seconds=1.0,
            provider_call_sid="CA123456789",
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.update_status.return_value = failed_execution

        # Mock execution log for timeout
        log_entry = ExecutionLogEntity(
            id=uuid4(),
            execution_id=execution.id,
            step_number=1,
            expected_text="1",
            actual_transcription=None,
            confidence_score=None,
            action_taken="TIMEOUT",
            created_at=datetime.now(timezone.utc),
        )
        mock_execution_log_repo.create.return_value = log_entry

        # Execute
        result = await use_case.execute(test_case_id, phone_number, webhook_url)
        
        # Assertions: immediate response should be RUNNING
        assert result.status == "RUNNING"
        assert result.id == execution.id
        
        # Give potential background task a window
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_execute_passive_long_step_timeout_fallback_accepts_match(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_execution_log_repo,
        mock_call_provider,
        mock_asr_provider,
        mock_call_session_store,
        monkeypatch,
    ):
        """Passive long step should pass on timeout when best similarity is good enough."""
        test_case_id = uuid4()
        phone_number = "+1234567890"
        webhook_url = "http://localhost:8000/webhooks/twilio/voice"

        expected_long_text = (
            "bienvenido a la linea de servicio al cliente emcali le informamos que por razones de calidad "
            "su llamada podra ser grabada o monitoreada senor usuario le informamos que sus datos seran "
            "tratados conforme a las disposiciones establecidas en la ley mil quinientos ochenta y uno "
            "de dos mil doce proteccion de datos personales"
        )

        flow_script = [{"step": 1, "listen": expected_long_text, "action": None}]
        test_case = TestCaseEntity(
            id=test_case_id,
            ivr_architecture_id=uuid4(),
            name="Passive Timeout Fallback",
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

        monkeypatch.setattr(state_machine_module, "STEP_TIMEOUT_SECONDS", 0.1)
        monkeypatch.setattr(execute_module, "PASSIVE_TIMEOUT_FALLBACK_RATIO", 0.72)
        monkeypatch.setattr(execute_module, "PASSIVE_TIMEOUT_FALLBACK_MIN_TOKENS", 8)

        mock_call_session_store.try_dequeue_audio.return_value = b"audio_data"

        async def _set_handler(cb):
            mock_asr_provider._cb = cb

        sent_once = {"value": False}

        async def _send_audio(_chunk):
            if getattr(mock_asr_provider, "_cb", None) and not sent_once["value"]:
                sent_once["value"] = True
                await mock_asr_provider._cb(
                    "a la linea de servicio al cliente emcali le informamos por razones de calidad su llamada",
                    True,
                )

        mock_asr_provider.set_transcript_handler.side_effect = _set_handler
        mock_asr_provider.send_audio.side_effect = _send_audio

        # Force similarity below strict 85% but above passive timeout fallback threshold.
        use_case._evaluate_transcription = MagicMock(return_value=(0.7409, Decimal("74.09"), False))

        passed_execution = TestExecutionEntity(
            id=execution.id,
            test_case_id=test_case_id,
            status="PASSED",
            duration_seconds=1.0,
            provider_call_sid="CA123456789",
            executed_at=datetime.now(timezone.utc),
        )
        mock_test_execution_repo.update_status.return_value = passed_execution

        result = await use_case.execute(test_case_id, phone_number, webhook_url)
        assert result.status == "RUNNING"

        await asyncio.sleep(0.4)

        passed_status_updates = [
            call
            for call in mock_test_execution_repo.update_status.call_args_list
            if call.kwargs.get("status") == "PASSED"
        ]
        assert passed_status_updates, "Expected execution to finish as PASSED using timeout fallback"

        logged_actions = [
            call.args[0].action_taken
            for call in mock_execution_log_repo.create.call_args_list
            if call.args
        ]
        assert any("timeout fallback accepted" in action.lower() for action in logged_actions)


class TestExecuteTestCaseSimilarityHelpers:
    """Tests granulares para helpers puros de similitud."""

    def test_normalize_similarity_text_removes_accents_and_punctuation(self, use_case):
        raw = "  ¡Óptimo,   menú número 1!  "

        normalized = use_case._normalize_similarity_text(raw)

        assert normalized == "optimo menu numero 1"

    def test_tokenize_for_similarity_removes_stopwords(self, use_case):
        text = "para ventas marque uno por favor"

        tokens = use_case._tokenize_for_similarity(text)

        # "para", "uno" y "por" son stopwords; las palabras de señal permanecen.
        assert tokens == ["ventas", "marque", "favor"]

    def test_ordered_token_coverage_returns_partial_ratio(self, use_case):
        expected_tokens = ["hola", "mundo", "ivr"]
        candidate_tokens = ["foo", "hola", "x", "mundo"]

        coverage = use_case._ordered_token_coverage(expected_tokens, candidate_tokens)

        assert coverage == pytest.approx(2 / 3)

    def test_ordered_token_coverage_returns_zero_on_empty_inputs(self, use_case):
        assert use_case._ordered_token_coverage([], ["hola"]) == 0.0
        assert use_case._ordered_token_coverage(["hola"], []) == 0.0

    def test_evaluate_transcription_fast_path_exact_substring(self, use_case):
        ratio, confidence, is_match = use_case._evaluate_transcription(
            expected_text="para ventas marque 2",
            transcription="bienvenido para ventas marque 2 gracias",
        )

        assert ratio == 1.0
        assert confidence == Decimal("100.00")
        assert is_match is True

    def test_evaluate_transcription_respects_threshold_parameter(self, use_case):
        expected = "hola mundo adios"
        transcription = "hola mundo"

        ratio, _, _ = use_case._evaluate_transcription(
            expected_text=expected,
            transcription=transcription,
            threshold=0.0,
        )

        high_threshold = min(1.0, ratio + 0.01)
        low_threshold = max(0.0, ratio - 0.01)

        ratio_high, _, is_match_high = use_case._evaluate_transcription(
            expected_text=expected,
            transcription=transcription,
            threshold=high_threshold,
        )
        ratio_low, _, is_match_low = use_case._evaluate_transcription(
            expected_text=expected,
            transcription=transcription,
            threshold=low_threshold,
        )

        assert ratio_high == pytest.approx(ratio)
        assert ratio_low == pytest.approx(ratio)
        assert is_match_high is False
        assert is_match_low is True
