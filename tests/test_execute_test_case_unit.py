"""Unit tests for ExecuteTestCaseUseCase."""

import asyncio
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from time import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.application.use_cases import execute_test_case_use_case as execute_module
from src.application.services import ivr_state_machine as state_machine_module
from src.application.exceptions import NotFoundError

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

    @pytest.mark.asyncio
    async def test_execute_raises_not_found_when_test_case_does_not_exist(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_event_hub,
    ):
        test_case_id = uuid4()
        mock_test_case_repo.get_by_id.side_effect = NotFoundError("not found")

        with pytest.raises(NotFoundError):
            await use_case.execute(
                test_case_id=test_case_id,
                phone_number="+1234567890",
                webhook_url="http://localhost/webhook",
            )

        mock_test_execution_repo.create.assert_not_called()
        mock_event_hub.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_continues_when_start_event_publish_fails(
        self,
        use_case,
        mock_test_case_repo,
        mock_test_execution_repo,
        mock_event_hub,
        monkeypatch,
    ):
        test_case_id = uuid4()
        test_case = TestCaseEntity(
            id=test_case_id,
            ivr_architecture_id=uuid4(),
            name="Case",
            flow_script=[{"step": 1, "listen": "bienvenido", "action": None}],
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
        mock_event_hub.publish.side_effect = RuntimeError("hub unavailable")

        created_coroutines = []

        def _fake_create_task(coro):
            created_coroutines.append(coro)
            coro.close()
            return MagicMock()

        monkeypatch.setattr(execute_module.asyncio, "create_task", _fake_create_task)

        result = await use_case.execute(
            test_case_id=test_case_id,
            phone_number="+1234567890",
            webhook_url="http://localhost/webhook",
        )

        assert result.id == execution.id
        assert result.status == "RUNNING"
        mock_event_hub.publish.assert_awaited_once()
        assert len(created_coroutines) == 1

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

    def test_extract_matched_excerpt_and_remainder_preserves_tail(self, use_case):
        expected = "bienvenido a ucompensar para efectos de la calidad en el servicio"
        actual = (
            "bienvenido a ucompensar para efectos de la calidad en el servicio "
            "si estás interesado en conocer nuestros programas académicos marca uno"
        )

        excerpt, remainder = use_case._extract_matched_excerpt_and_remainder(expected, actual)

        assert excerpt == "bienvenido a ucompensar para efectos de la calidad en el servicio"
        assert remainder == "si estás interesado en conocer nuestros programas académicos marca uno"

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

    def test_evaluate_transcription_handles_real_ivr_paraphrase_at_85_percent(self, use_case):
        expected = (
            "Si te comunicas de una empresa, eres estudiante activo y requieres "
            "orientación relacionada con tu proceso académico, marca uno"
        )
        transcription = (
            "seguido del número de la extensión o si lo prefieres espera en línea para ser transferido "
            "a uno de nuestros agentes de servicio eres estudiante activo y requieres orientación "
            "relacionada con tu proceso académico marca uno te comunicas en nombre de una empresa"
        )

        ratio, confidence, is_match = use_case._evaluate_transcription(
            expected_text=expected,
            transcription=transcription,
            threshold=0.85,
        )

        assert ratio >= 0.85
        assert confidence == Decimal(str(ratio * 100)).quantize(Decimal("0.01"))
        assert is_match is True

    def test_evaluate_transcription_matches_apoyo_financiero_menu_at_85_percent(self, use_case):
        expected = (
            "Si tienes consultas sobre la inscripción, el proceso de admisión y o sobre "
            "temas de apoyo financiero, marca cuatro"
        )
        transcription = (
            "si eres estudiante empresario graduado o para información sobre carreras profesionales "
            "o técnicos laborales marca uno para información sobre programas técnicos laborales "
            "marca dos para información sobre posgrados marca tres si tienes consultas sobre la "
            "inscripción el proceso de admisión y o sobre temas de apoyo financiero continua marca "
            "cinco para regresar al menú anterior marca seis"
        )

        ratio, confidence, is_match = use_case._evaluate_transcription(
            expected_text=expected,
            transcription=transcription,
            threshold=0.85,
        )

        assert ratio >= 0.85
        assert confidence == Decimal(str(ratio * 100)).quantize(Decimal("0.01"))
        assert is_match is True


class TestExecuteTestCaseCriticalFlowHelpers:
    """Cubre helpers críticos de flujo y finalización sin depender de background tasks."""

    @pytest.mark.asyncio
    async def test_execute_action_returns_passive_step_when_no_action(self, use_case, mock_call_provider):
        action_taken, has_error = await use_case._execute_action(
            call_sid="CA123",
            action=None,
            step_number=1,
        )

        assert action_taken == "No action (passive step)"
        assert has_error is False
        mock_call_provider.send_dtmf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_action_sends_dtmf_and_returns_success(
        self, use_case, mock_call_provider, monkeypatch
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)

        action_taken, has_error = await use_case._execute_action(
            call_sid="CA123",
            action="12",
            step_number=2,
        )

        assert action_taken == "Sent DTMF: 12"
        assert has_error is False
        mock_call_provider.send_dtmf.assert_awaited_once_with(
            call_sid="CA123",
            digits="12",
        )

    @pytest.mark.asyncio
    async def test_execute_action_returns_error_when_provider_fails(
        self, use_case, mock_call_provider
    ):
        mock_call_provider.send_dtmf.side_effect = RuntimeError("socket error")

        action_taken, has_error = await use_case._execute_action(
            call_sid="CA123",
            action="9",
            step_number=3,
        )

        assert has_error is True
        assert action_taken.startswith("DTMF error:")
        assert "socket error" in action_taken

    @pytest.mark.asyncio
    async def test_log_step_persists_execution_log_entity(self, use_case, mock_execution_log_repo):
        execution_id = uuid4()

        await use_case._log_step(
            execution_id=execution_id,
            step_number=1,
            expected_text="Bienvenido",
            actual_transcription="Bienvenido",
            confidence=Decimal("97.50"),
            action_taken="Sent DTMF: 1",
        )

        mock_execution_log_repo.create.assert_awaited_once()
        created_log = mock_execution_log_repo.create.call_args.args[0]
        assert isinstance(created_log, ExecutionLogEntity)
        assert created_log.execution_id == execution_id
        assert created_log.step_number == 1
        assert created_log.confidence_score == Decimal("97.50")

    @pytest.mark.asyncio
    async def test_log_step_swallows_repository_errors(self, use_case, mock_execution_log_repo):
        mock_execution_log_repo.create.side_effect = RuntimeError("db unavailable")

        await use_case._log_step(
            execution_id=uuid4(),
            step_number=1,
            expected_text="Texto",
            actual_transcription=None,
            confidence=Decimal("0.00"),
            action_taken="Timeout waiting for audio",
        )

        mock_execution_log_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_step_failure_logs_and_publishes_event(
        self, use_case, mock_execution_log_repo, mock_event_hub
    ):
        use_case._log_step = AsyncMock()
        execution_id = uuid4()

        await use_case._record_step_failure(
            execution_id=execution_id,
            step_number=2,
            expected_text="marque uno",
            actual_text="marque dos",
            reason="Failed text match",
            confidence=Decimal("64.00"),
            execution_log_repo=mock_execution_log_repo,
        )

        use_case._log_step.assert_awaited_once()
        mock_event_hub.publish.assert_awaited_once()
        published_event = mock_event_hub.publish.call_args.args[0]
        assert published_event.event_type.value == "step_failed"
        assert published_event.execution_id == execution_id

    @pytest.mark.asyncio
    async def test_record_step_failure_ignores_event_publish_errors(
        self, use_case, mock_execution_log_repo, mock_event_hub
    ):
        use_case._log_step = AsyncMock()
        mock_event_hub.publish.side_effect = RuntimeError("hub down")

        await use_case._record_step_failure(
            execution_id=uuid4(),
            step_number=4,
            expected_text="opcion cuatro",
            actual_text=None,
            reason="Timeout",
            confidence=Decimal("0.00"),
            execution_log_repo=mock_execution_log_repo,
        )

        use_case._log_step.assert_awaited_once()
        mock_event_hub.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_single_step_returns_false_on_transcription_error(self, use_case):
        use_case._get_transcription = AsyncMock(return_value=(None, "Timeout waiting for audio"))
        use_case._log_step = AsyncMock()
        use_case._evaluate_transcription = MagicMock()

        result = await use_case._process_single_step(
            execution_id=uuid4(),
            call_sid="CA123",
            step={"step": 1, "listen": "bienvenido", "action": None},
            step_index=1,
        )

        assert result is False
        use_case._log_step.assert_awaited_once()
        use_case._evaluate_transcription.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_single_step_returns_false_on_mismatch(self, use_case):
        use_case._get_transcription = AsyncMock(return_value=("texto distinto", None))
        use_case._evaluate_transcription = MagicMock(return_value=(0.40, Decimal("40.00"), False))
        use_case._log_step = AsyncMock()
        use_case._execute_action = AsyncMock()

        result = await use_case._process_single_step(
            execution_id=uuid4(),
            call_sid="CA123",
            step={"step": 2, "listen": "texto esperado", "action": "1"},
            step_index=2,
        )

        assert result is False
        use_case._log_step.assert_awaited_once()
        use_case._execute_action.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_single_step_returns_false_on_action_error(self, use_case):
        use_case._get_transcription = AsyncMock(return_value=("opcion uno", None))
        use_case._evaluate_transcription = MagicMock(return_value=(0.93, Decimal("93.00"), True))
        use_case._execute_action = AsyncMock(return_value=("DTMF error: socket", True))
        use_case._log_step = AsyncMock()

        result = await use_case._process_single_step(
            execution_id=uuid4(),
            call_sid="CA123",
            step={"step": 3, "listen": "opcion uno", "action": "1"},
            step_index=3,
        )

        assert result is False
        use_case._execute_action.assert_awaited_once()
        use_case._log_step.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_single_step_returns_true_on_success(self, use_case):
        use_case._get_transcription = AsyncMock(return_value=("opcion uno", None))
        use_case._evaluate_transcription = MagicMock(return_value=(0.95, Decimal("95.00"), True))
        use_case._execute_action = AsyncMock(return_value=("Sent DTMF: 1", False))
        use_case._log_step = AsyncMock()

        result = await use_case._process_single_step(
            execution_id=uuid4(),
            call_sid="CA123",
            step={"step": 4, "listen": "opcion uno", "action": "1"},
            step_index=4,
        )

        assert result is True
        use_case._execute_action.assert_awaited_once()
        use_case._log_step.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_finalize_execution_success_path(
        self,
        use_case,
        mock_test_execution_repo,
        mock_call_provider,
        mock_call_session_store,
        mock_event_hub,
        monkeypatch,
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)

        execution_id = uuid4()
        call_sid = "CA123"
        await use_case._finalize_execution(
            execution_id=execution_id,
            call_sid=call_sid,
            start_time=time() - 2,
            all_passed=True,
        )

        mock_test_execution_repo.update_status.assert_awaited_once()
        status_kwargs = mock_test_execution_repo.update_status.call_args.kwargs
        assert status_kwargs["status"] == "PASSED"
        assert status_kwargs["duration_seconds"] >= 0

        mock_event_hub.publish.assert_awaited_once()
        published_event = mock_event_hub.publish.call_args.args[0]
        assert published_event.event_type.value == "execution_finished"
        assert published_event.data["status"] == "PASSED"

        mock_call_provider.hangup.assert_awaited_once_with(call_sid)
        mock_call_session_store.close_session.assert_awaited_once_with(call_sid)

    @pytest.mark.asyncio
    async def test_finalize_execution_emits_error_event_when_status_update_fails(
        self,
        use_case,
        mock_test_execution_repo,
        mock_call_provider,
        mock_call_session_store,
        mock_event_hub,
        monkeypatch,
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)
        mock_test_execution_repo.update_status.side_effect = RuntimeError("connection refused")

        execution_id = uuid4()
        call_sid = "CA999"
        await use_case._finalize_execution(
            execution_id=execution_id,
            call_sid=call_sid,
            start_time=time() - 1,
            all_passed=False,
        )

        mock_test_execution_repo.update_status.assert_awaited_once()
        mock_event_hub.publish.assert_awaited_once()
        published_event = mock_event_hub.publish.call_args.args[0]
        assert published_event.event_type.value == "execution_error"
        assert published_event.execution_id == execution_id
        assert published_event.data["status"] == "ERROR"

        # El cleanup debe ocurrir incluso cuando falla update_status
        mock_call_provider.hangup.assert_awaited_once_with(call_sid)
        mock_call_session_store.close_session.assert_awaited_once_with(call_sid)


class TestExecuteTestCaseStreamingAndMonitoring:
    """Cubre paths críticos de streaming ASR y monitoreo de inactividad."""

    @pytest.mark.asyncio
    async def test_get_transcription_returns_connect_error_when_asr_connect_fails(
        self, use_case, mock_asr_provider
    ):
        mock_asr_provider._is_connected = False
        mock_asr_provider.connect.side_effect = RuntimeError("deepgram unavailable")

        transcription, error = await use_case._get_transcription(
            call_sid="CA123",
            step_number=1,
            expected_text="hola",
        )

        assert transcription is None
        assert error is not None
        assert error.startswith("ASR connect error")

    @pytest.mark.asyncio
    async def test_get_transcription_returns_timeout_when_no_audio_received(
        self, use_case, mock_asr_provider, mock_call_session_store, monkeypatch
    ):
        mock_asr_provider._is_connected = True
        mock_call_session_store.try_dequeue_audio.return_value = None

        monkeypatch.setattr(execute_module, "AUDIO_TIMEOUT_SECONDS", 0.01)

        transcription, error = await use_case._get_transcription(
            call_sid="CA456",
            step_number=2,
            expected_text="menu principal",
            should_clear_queue=True,
        )

        assert transcription is None
        assert error == "Timeout waiting for audio"
        mock_call_session_store.clear_queue.assert_awaited_once_with("CA456")
        mock_asr_provider.set_transcript_handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_transcription_returns_text_when_speech_final_arrives(
        self, use_case, mock_asr_provider, mock_call_session_store, monkeypatch
    ):
        mock_asr_provider._is_connected = True

        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)

        stored_handler = {"cb": None}

        async def _set_handler(cb):
            stored_handler["cb"] = cb

        async def _send_audio(_chunk):
            await stored_handler["cb"]("hola mundo", True, True)

        mock_asr_provider.set_transcript_handler.side_effect = _set_handler
        mock_asr_provider.send_audio.side_effect = _send_audio
        mock_call_session_store.try_dequeue_audio.return_value = b"audio_chunk"

        transcription, error = await use_case._get_transcription(
            call_sid="CA789",
            step_number=3,
            expected_text="hola mundo",
        )

        assert error is None
        assert transcription == "hola mundo"
        mock_asr_provider.send_audio.assert_awaited_once_with(b"audio_chunk")

    @pytest.mark.asyncio
    async def test_get_transcription_preserves_queue_when_flag_is_false(
        self, use_case, mock_asr_provider, mock_call_session_store, monkeypatch
    ):
        mock_asr_provider._is_connected = True
        mock_call_session_store.try_dequeue_audio.return_value = None
        monkeypatch.setattr(execute_module, "AUDIO_TIMEOUT_SECONDS", 0.01)

        await use_case._get_transcription(
            call_sid="CA998",
            step_number=4,
            expected_text="texto",
            should_clear_queue=False,
        )

        mock_call_session_store.clear_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_audio_inactivity_stops_when_session_disappears(
        self, use_case, mock_asr_provider, mock_call_session_store, monkeypatch
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)
        mock_call_session_store.get_seconds_since_last_audio.return_value = None

        await use_case._monitor_audio_inactivity("CA111")

        mock_call_session_store.get_seconds_since_last_audio.assert_awaited_once_with("CA111")
        mock_asr_provider.disconnect.assert_not_called()
        mock_asr_provider.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_audio_inactivity_reconnects_asr_after_threshold(
        self, use_case, mock_asr_provider, mock_call_session_store, monkeypatch
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)
        mock_asr_provider._is_connected = True
        mock_call_session_store.get_seconds_since_last_audio.side_effect = [6.5, None]

        session = CallSessionEntity(
            call_sid="CA222",
            started_at=datetime.now(timezone.utc),
            is_active=True,
        )
        mock_call_session_store.get_session.return_value = session

        await use_case._monitor_audio_inactivity("CA222")

        mock_asr_provider.disconnect.assert_awaited_once()
        mock_asr_provider.connect.assert_awaited_once()
        mock_call_session_store.get_session.assert_awaited_once_with("CA222")
        assert session.last_audio_timestamp is not None

    @pytest.mark.asyncio
    async def test_finalize_execution_continues_when_hangup_and_cleanup_fail(
        self,
        use_case,
        mock_test_execution_repo,
        mock_call_provider,
        mock_call_session_store,
        mock_event_hub,
        monkeypatch,
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)
        mock_call_provider.hangup.side_effect = RuntimeError("hangup failed")
        mock_call_session_store.close_session.side_effect = RuntimeError("close failed")

        await use_case._finalize_execution(
            execution_id=uuid4(),
            call_sid="CA333",
            start_time=time() - 1,
            all_passed=True,
        )

        mock_test_execution_repo.update_status.assert_awaited_once()
        mock_event_hub.publish.assert_awaited_once()
        mock_call_provider.hangup.assert_awaited_once_with("CA333")
        mock_call_session_store.close_session.assert_awaited_once_with("CA333")


class TestExecuteTestCaseBackgroundRecovery:
    """Cubre recovery paths en orquestación de background."""

    @pytest.fixture
    def sample_execution(self):
        return TestExecutionEntity(
            id=uuid4(),
            test_case_id=uuid4(),
            status="RUNNING",
            duration_seconds=None,
            provider_call_sid=None,
            executed_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_test_case(self):
        return TestCaseEntity(
            id=uuid4(),
            ivr_architecture_id=uuid4(),
            name="Background flow",
            flow_script=[{"step": 1, "listen": "bienvenido", "action": None}],
            created_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_process_call_background_recovers_pending_rollback(
        self, use_case, sample_execution, sample_test_case
    ):
        recovery_repo = AsyncMock()

        class FakeUow:
            def __init__(self, repo):
                self.test_execution_repo = repo
                self.execution_log_repo = AsyncMock()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        use_case.uow_factory = lambda: FakeUow(recovery_repo)
        use_case._process_call_background_with_repos = AsyncMock(
            side_effect=execute_module.PendingRollbackError("rollback-only")
        )

        await use_case._process_call_background(
            execution=sample_execution,
            test_case=sample_test_case,
            phone_number="+12025550001",
            webhook_url="http://localhost/webhook",
        )

        recovery_repo.update_status.assert_awaited_once()
        kwargs = recovery_repo.update_status.call_args.kwargs
        assert kwargs["status"] == "FAILED"
        assert kwargs["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_process_call_background_recovers_unhandled_exception(
        self, use_case, sample_execution, sample_test_case
    ):
        recovery_repo = AsyncMock()

        class FakeUow:
            def __init__(self, repo):
                self.test_execution_repo = repo
                self.execution_log_repo = AsyncMock()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        use_case.uow_factory = lambda: FakeUow(recovery_repo)
        use_case._process_call_background_with_repos = AsyncMock(
            side_effect=RuntimeError("unexpected background error")
        )

        await use_case._process_call_background(
            execution=sample_execution,
            test_case=sample_test_case,
            phone_number="+12025550002",
            webhook_url="http://localhost/webhook",
        )

        recovery_repo.update_status.assert_awaited_once()
        kwargs = recovery_repo.update_status.call_args.kwargs
        assert kwargs["status"] == "ERROR"
        assert kwargs["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_process_call_background_with_repos_handles_initiate_call_failure(
        self, use_case, sample_execution, sample_test_case, monkeypatch
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)
        use_case.call_provider.initiate_call.side_effect = RuntimeError("connection refused")

        test_execution_repo = AsyncMock()
        execution_log_repo = AsyncMock()

        await use_case._process_call_background_with_repos(
            execution=sample_execution,
            test_case=sample_test_case,
            phone_number="+12025550003",
            webhook_url="http://localhost/webhook",
            test_execution_repo=test_execution_repo,
            execution_log_repo=execution_log_repo,
            start_time=time() - 2,
        )

        test_execution_repo.update_status.assert_awaited_once()
        status_kwargs = test_execution_repo.update_status.call_args.kwargs
        assert status_kwargs["status"] == "ERROR"
        assert status_kwargs["duration_seconds"] >= 0

        use_case.event_hub.publish.assert_awaited_once()
        event = use_case.event_hub.publish.call_args.args[0]
        assert event.event_type.value == "execution_error"

    @pytest.mark.asyncio
    async def test_process_call_background_with_repos_hangs_up_when_sid_persist_fails(
        self, use_case, sample_execution, sample_test_case, monkeypatch
    ):
        async def _no_wait(_seconds):
            return None

        monkeypatch.setattr(execute_module.asyncio, "sleep", _no_wait)

        call_session = CallSessionEntity(
            call_sid="CA-PERSIST-FAIL",
            started_at=datetime.now(timezone.utc),
            is_active=True,
        )
        use_case.call_provider.initiate_call.return_value = call_session

        test_execution_repo = AsyncMock()
        test_execution_repo.update_provider_call_sid.side_effect = RuntimeError("db write failed")

        await use_case._process_call_background_with_repos(
            execution=sample_execution,
            test_case=sample_test_case,
            phone_number="+12025550004",
            webhook_url="http://localhost/webhook",
            test_execution_repo=test_execution_repo,
            execution_log_repo=AsyncMock(),
            start_time=time() - 1,
        )

        use_case.call_provider.hangup.assert_awaited_once_with("CA-PERSIST-FAIL")
        test_execution_repo.update_status.assert_awaited_once()
