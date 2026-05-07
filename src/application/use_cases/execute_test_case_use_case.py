"""Use case para ejecutar un test case — orquestación de llamadas y pasos."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
import re
from time import time
from uuid import UUID
from typing import Callable, Optional
import unicodedata
import socket

from sqlalchemy.exc import PendingRollbackError

from src.domain.entities.execution_log import ExecutionLogEntity
from src.domain.entities.test_case import TestCaseEntity
from src.domain.entities.test_execution import TestExecutionEntity
from src.domain.ports.asr_provider import IASRProvider
from src.domain.ports.call_provider import ICallProvider
from src.domain.repositories.execution_log_repository import IExecutionLogRepository
from src.domain.repositories.test_case_repository import ITestCaseRepository
from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.application.exceptions import NotFoundError, ExternalDependencyError
from src.application.dtos.realtime_events import ExecutionEvent
from src.application.services.ivr_state_machine import (
    IVRStateMachine,
    SILENCE_THRESHOLD_SECONDS,
    STEP_TIMEOUT_SECONDS,
    EXTREME_SILENCE_THRESHOLD_SECONDS,
    GRACE_PERIOD_AFTER_DTMF_SECONDS,
    SIMILARITY_THRESHOLD,
    EARLY_EXIT_THRESHOLD,
    EARLY_EXIT_SILENCE_SECONDS,
)
from src.application.utils.error_utils import (
    classify_error_category,
    extract_deepgram_error_metadata,
    format_log_fields,
    get_user_friendly_error_message,
    sanitize_error_message,
)
from src.infrastructure.call_session_store import CallSessionStore
from src.infrastructure.database.uow import UnitOfWork
from src.infrastructure.logger import get_logger
from src.infrastructure.execution_event_hub import ExecutionEventHub

logger = get_logger(__name__)

# Constantes
AUDIO_TIMEOUT_SECONDS = 30.0
STREAM_POLL_SECONDS = 0.5
REPETITION_THRESHOLD = 0.50  # 50% - similitud para detectar si el IVR está repitiendo el menú
STEP_STAGNATION_SECONDS = 12.0
STEP_STAGNATION_MAX_RATIO = 0.45
STEP_STAGNATION_MIN_SILENCE_SECONDS = 4.0
PASSIVE_TIMEOUT_FALLBACK_RATIO = 0.72
PASSIVE_TIMEOUT_FALLBACK_MIN_TOKENS = 18

# Stopwords comunes para robustecer similitud ante variaciones ASR en frases largas.
SIMILARITY_STOPWORDS = {
    "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "durante",
    "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "es", "esa", "ese",
    "esta", "este", "esto", "ha", "hasta", "la", "las", "le", "les", "lo", "los",
    "mas", "mi", "no", "o", "para", "pero", "por", "que", "se", "ser", "si",
    "sin", "su", "sus", "te", "tu", "un", "una", "uno", "y",
}


class ExecuteTestCaseUseCase:
    """Use case que orquesta la ejecución de un test case contra un IVR."""

    def __init__(
        self,
        test_case_repo: ITestCaseRepository,
        test_execution_repo: ITestExecutionRepository,
        execution_log_repo: IExecutionLogRepository,
        call_provider: ICallProvider,
        asr_provider: IASRProvider,
        call_session_store: CallSessionStore,
        event_hub: ExecutionEventHub,
        uow_factory: Callable[[], UnitOfWork] | None = None,
    ) -> None:
        """Inicializa el use case con dependencias.
        
        Args:
            test_case_repo: Repositorio de test cases
            test_execution_repo: Repositorio de ejecuciones
            execution_log_repo: Repositorio de logs de steps
            call_provider: Proveedor de telefonía (Twilio)
            asr_provider: Proveedor de transcripción (Deepgram, etc)
            call_session_store: Store de sesiones activas
            event_hub: Hub para publicar eventos en tiempo real
            uow_factory: Factory para UnitOfWork en background
        """
        self.test_case_repo = test_case_repo
        self.test_execution_repo = test_execution_repo
        self.execution_log_repo = execution_log_repo
        self.call_provider = call_provider
        self.asr_provider = asr_provider
        self.call_session_store = call_session_store
        self.event_hub = event_hub
        self.uow_factory = uow_factory

    async def _check_network_preflight(self) -> None:
        """Check network dependencies before starting execution."""
        hosts_to_check = ["api.deepgram.com", "api.twilio.com"]
        max_attempts = 3
        base_delay_seconds = 0.2
        for host in hosts_to_check:
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    # Resolve host to verify DNS/network
                    loop = asyncio.get_running_loop()
                    await loop.getaddrinfo(host, 443)
                    if attempt > 1:
                        logger.info(
                            "Preflight network check recovered"
                            f" | {format_log_fields({'host': host, 'attempt': attempt, 'max_attempts': max_attempts})}"
                        )
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    error_category = classify_error_category(e)
                    retryable = isinstance(e, socket.gaierror) or error_category in {
                        "network",
                        "timeout",
                        "unavailable",
                    }
                    delay_seconds = base_delay_seconds * (2 ** (attempt - 1))
                    log_fields = format_log_fields(
                        {
                            "host": host,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "delay_ms": int(delay_seconds * 1000),
                            "error_category": error_category,
                        }
                    )
                    if attempt < max_attempts and retryable:
                        logger.warning(
                            "Preflight network check failed, retrying"
                            f" | {log_fields} error={sanitize_error_message(e)}"
                        )
                        await asyncio.sleep(delay_seconds)
                        continue

                    logger.error(
                        "Preflight network check failed, aborting"
                        f" | {log_fields} error={sanitize_error_message(e)}"
                    )
                    break

            if last_error is not None:
                raise ExternalDependencyError(
                    f"Error de red: No se pudo contactar al proveedor de telefonía u transcripción ({host}). "
                    f"Revisa tu conexión a internet o los servidores DNS."
                )

    async def execute(
        self, test_case_id: UUID, phone_number: str, webhook_url: str
    ) -> TestExecutionEntity:
        """Síncronamente crea la ejecución y lanza el proceso en background.
        
        Retorna la entidad RUNNING inmediatamente.
        """
        logger.info(f"Starting test case execution setup: {test_case_id}")
        
        # 0. Preflight checks - early fail on DNS / Network issues
        await self._check_network_preflight()

        # 1. Obtener test case
        try:
            test_case = await self.test_case_repo.get_by_id(test_case_id)
        except NotFoundError:
            logger.warning(f"Test case not found: {test_case_id}")
            raise

        # 2. Crear ejecución inicial sincrónicamente para devolverla al HTTP router
        execution = await self.test_execution_repo.create(
            test_case_id=test_case_id,
            status="RUNNING",
            provider_call_sid=None,
        )
        logger.info(f"Execution created: {execution.id}")

        # Emitir evento de inicio
        try:
            start_event = ExecutionEvent.execution_started(execution.id)
            await self.event_hub.publish(start_event)
        except Exception as e:
            logger.error(f"Error publicando execution_started: {e}")

        # 3. Lanzar orquestación pesada en background
        asyncio.create_task(
            self._process_call_background(
                execution=execution,
                test_case=test_case,
                phone_number=phone_number,
                webhook_url=webhook_url,
            )
        )
        
        return execution

    async def _process_call_background(
        self, 
        execution: TestExecutionEntity, 
        test_case: TestCaseEntity, 
        phone_number: str,
        webhook_url: str
    ) -> None:
        """Lógica principal de orquestación en background con manejo de errores."""
        start_time = time()
        logger.info(f"Background processing started for execution: {execution.id}")

        if self.uow_factory is None:
            await self._process_call_background_with_repos(
                execution=execution,
                test_case=test_case,
                phone_number=phone_number,
                webhook_url=webhook_url,
                test_execution_repo=self.test_execution_repo,
                execution_log_repo=self.execution_log_repo,
                start_time=start_time,
            )
            return

        try:
            async with self.uow_factory() as uow:
                await self._process_call_background_with_repos(
                    execution=execution,
                    test_case=test_case,
                    phone_number=phone_number,
                    webhook_url=webhook_url,
                    test_execution_repo=uow.test_execution_repo,
                    execution_log_repo=uow.execution_log_repo,
                    start_time=start_time,
                )
        except PendingRollbackError as e:
            logger.error(
                f"PendingRollbackError in background task for execution {execution.id}: {sanitize_error_message(e)}"
            )
            # Session rolled back → use a fresh session to force status update to FAILED
            try:
                async with self.uow_factory() as uow:
                    duration_seconds = int(time() - start_time)
                    await uow.test_execution_repo.update_status(
                        execution.id,
                        status="FAILED",
                        duration_seconds=duration_seconds,
                    )
                    logger.info(
                        f"[Recovery] Forced execution {execution.id} status to FAILED after PendingRollbackError"
                    )
            except Exception as recovery_err:
                logger.error(
                    f"Failed to recover execution {execution.id} status after PendingRollbackError: {recovery_err}"
                )
        except Exception as e:
            logger.error(
                f"Unhandled exception in background task for execution {execution.id}: {sanitize_error_message(e)}",
                exc_info=True
            )
            # ✅ Force status update to capture any unhandled background exceptions
            try:
                async with self.uow_factory() as uow:
                    duration_seconds = int(time() - start_time)
                    await uow.test_execution_repo.update_status(
                        execution.id,
                        status="ERROR",
                        duration_seconds=duration_seconds,
                    )
                    logger.info(
                        f"[Recovery] Forced execution {execution.id} status to ERROR after unhandled exception"
                    )
            except Exception as recovery_err:
                logger.error(
                    f"Failed to recover execution {execution.id} status after unhandled exception: {recovery_err}"
                )

    async def _process_call_background_with_repos(
        self,
        execution: TestExecutionEntity,
        test_case: TestCaseEntity,
        phone_number: str,
        webhook_url: str,
        test_execution_repo: ITestExecutionRepository,
        execution_log_repo: IExecutionLogRepository,
        start_time: float,
    ) -> None:
        """Procesa la orquestación con repositorios y sesión explícitos."""
        asr_connected = False
        # 1. Iniciar llamada
        try:
            call_session = await self.call_provider.initiate_call(
                phone_number=phone_number,
                webhook_url=webhook_url,
            )
            execution = await test_execution_repo.update_provider_call_sid(
                execution.id,
                provider_call_sid=call_session.call_sid,
            )
            logger.info(f"Call initiated and persisted: {call_session.call_sid}")
        except Exception as e:
            self._log_flow_error(
                "Call initiation failed",
                level="error",
                error_type="provider",
                provider="twilio",
                operation="initiate_call",
                execution_id=str(execution.id),
                test_case_id=str(execution.test_case_id),
                error_category=classify_error_category(e),
                error_message=str(e),
            )
            duration = int(time() - start_time)
            try:
                await test_execution_repo.update_status(
                    execution.id,
                    status="ERROR",
                    duration_seconds=duration,
                )
                
                # ✅ Emitir evento de error al WebSocket con mensaje filtrado
                try:
                    # Log completo con detalle técnico para telemetry
                    logger.error(
                        f"Call initiation failed for execution {execution.id}",
                        exc_info=True,
                        extra={
                            "execution_id": str(execution.id),
                            "test_case_id": str(execution.test_case_id),
                            "raw_error": str(e),
                        }
                    )
                    
                    # Emitir mensaje filtrado y amigable al WebSocket
                    friendly_message = get_user_friendly_error_message(e)
                    error_event = ExecutionEvent.execution_error(
                        execution.id,
                        friendly_message,
                        duration,
                    )
                    await self.event_hub.publish(error_event)
                    logger.info(f"✓ execution_error event emitted for call initiation failure")
                    await asyncio.sleep(0.1)
                except Exception as e_hub:
                    logger.error(f"Could not emit execution_error event after call initiation failure: {e_hub}")
                    
            except Exception as e2:
                logger.error(
                    f"Failed to update execution {execution.id} status to ERROR after initiate_call failure: {e2}"
                )
            if "call_session" in locals():
                try:
                    await self.call_provider.hangup(call_session.call_sid)
                    logger.info(
                        "Call hung up after provider_call_sid persistence failure: %s",
                        call_session.call_sid,
                    )
                except Exception as e3:
                    logger.warning(
                        "Could not hang up call after provider_call_sid persistence failure: %s",
                        str(e3),
                    )
            return

        try:
            # 2. Esperar a que la llamada se conecte (el webhook debe crear la sesión).
            logger.info("Waiting for call to be answered and webhook to be received...")
            wait_time = 0.0
            max_wait_time = 45.0  # máximo 45 segundos para que contesten
            session_active = False

            while wait_time < max_wait_time:
                # Polling corto para ver si la sesión ya fue creada por el webhook
                if await self.call_session_store.is_session_active(call_session.call_sid):
                    session_active = True
                    break
                await asyncio.sleep(1.0)
                wait_time += 1.0

            if not session_active:
                self._log_flow_error(
                    "Call session timeout",
                    level="error",
                    error_type="flow",
                    reason_code="call_session_timeout",
                    execution_id=str(execution.id),
                    call_sid=call_session.call_sid,
                    waited_seconds=wait_time,
                )
                raise TimeoutError("Call was not answered or webhook was not received in time.")
            
            logger.info("Call answered and session active. Beginning step execution.")

            # Conexión ASR persistente para todo el test case
            try:
                logger.info("ASR: Conectando Deepgram para todo el flujo de pasos...")
                await self.asr_provider.connect(
                    encoding="mulaw",
                    sample_rate=8000,
                    endpointing=int(SILENCE_THRESHOLD_SECONDS * 1000),
                )
                asr_connected = True
                logger.info("ASR: Conexión Deepgram establecida (persistente)")
            except Exception as e:
                metadata = extract_deepgram_error_metadata(e)
                self._log_flow_error(
                    "ASR connect failed",
                    level="error",
                    error_type="provider",
                    provider="deepgram",
                    operation="connect",
                    reason_code="asr_connect_failed",
                    execution_id=str(execution.id),
                    call_sid=call_session.call_sid,
                    error_category=classify_error_category(e),
                    error_message=str(e),
                    **metadata,
                )
                raise

            # 2b. Lanzar monitor de inactividad de audio en background
            monitor_task: Optional[asyncio.Task] = None
            try:
                monitor_task = asyncio.create_task(
                    self._monitor_audio_inactivity(
                        call_sid=call_session.call_sid,
                    )
                )
                logger.debug(f"Audio inactivity monitor started for call {call_session.call_sid}")
            except Exception as e:
                logger.warning(f"Failed to start audio inactivity monitor: {e}")

            # 3. Procesar flujo con máquina de estados
            all_passed, full_call_transcript = await self._process_flow_with_state_machine(
                execution_id=execution.id,
                call_sid=call_session.call_sid,
                flow_script=test_case.flow_script,
                execution_log_repo=execution_log_repo,
            )
            
            # 3b. Detener monitor de audio
            if monitor_task:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            
            # 4. Guardar transcript completo en BD
            try:
                logger.info(f"Saving full_call_transcript to database | length={len(full_call_transcript)} chars")
                await test_execution_repo.update_full_call_transcript(
                    execution.id,
                    full_call_transcript,
                )
                logger.info(f"✓ Full transcript saved successfully")
            except Exception as e:
                logger.error(f"Failed to save full_call_transcript: {e}")
                # No es fatal, continuamos de todas formas

            # 5. Finalizar ejecución y colgar llamada
            logger.info(f"FLOW EXECUTION END | all_passed={all_passed} | execution_id={execution.id}")
            await self._finalize_execution(
                execution.id,
                call_session.call_sid,
                start_time,
                all_passed,
                test_execution_repo=test_execution_repo,
            )

        except Exception as e:
            self._log_flow_error(
                "Execution error",
                level="error",
                error_type="flow",
                reason_code="background_exception",
                execution_id=str(execution.id),
                error_category=classify_error_category(e),
                error_message=str(e),
            )
            duration = int(time() - start_time)
            
            # Actualizar estado en BD
            try:
                await test_execution_repo.update_status(
                    execution.id,
                    status="ERROR",
                    duration_seconds=duration,
                )
            except Exception as e2:
                logger.error(f"Could not update status after background error: {e2}")
            
            # ✅ IMPORTANTE: Emitir evento de error al WebSocket con mensaje filtrado
            try:
                # Log completo con detalle técnico para telemetry
                logger.error(
                    f"Background error during execution {execution.id}",
                    exc_info=True,
                    extra={
                        "execution_id": str(execution.id),
                        "raw_error": str(e),
                    }
                )
                
                # Emitir mensaje filtrado y amigable al WebSocket
                friendly_message = get_user_friendly_error_message(e)
                error_event = ExecutionEvent.execution_error(
                    execution.id,
                    friendly_message,
                    duration,
                )
                await self.event_hub.publish(error_event)
                logger.info(f"✓ execution_error event emitted to WebSocket for execution {execution.id}")
                await asyncio.sleep(0.1)  # Dar tiempo para que se entregue
            except Exception as e2:
                logger.error(f"Could not emit execution_error event: {e2}")

        finally:
            if asr_connected:
                try:
                    await self.asr_provider.disconnect()
                    logger.info("ASR: Desconectado persistentemente al final de la ejecución")
                except Exception as e:
                    logger.warning(f"ASR: Error al desconectar después de ejecución: {e}")

    async def _process_flow_with_state_machine(
        self,
        execution_id: UUID,
        call_sid: str,
        flow_script: list[dict],
        execution_log_repo: IExecutionLogRepository,
    ) -> tuple[bool, str]:
        """Procesa el flujo IVR completo usando máquina de estados continua.
        
        Retorna (all_passed, full_call_transcript).
        
        Implementa:
        - Un único bucle continuo escuchando ASR
        - Máquina de estados para detectar matching dinámico
        - Timeouts por step (15 segundos)
        - Soporte para steps sin action
        """
        logger.info(f"STATE MACHINE FLOW START | total_steps={len(flow_script)} | execution_id={execution_id}")
        
        # 1. Iniciar máquina de estados
        state_machine = IVRStateMachine(
            flow_script=flow_script,
            evaluate_transcription_fn=self._evaluate_transcription,
        )
        
        # 2. Configurar callback de ASR
        async def _on_transcript(text: str, is_final: bool, speech_final: bool = False) -> None:
            """Callback invocado por Deepgram cuando llega texto."""
            state_machine.accumulate_transcript_text(text, is_final, speech_final)
            
            # Emitir eventos de transcripción en tiempo real
            try:
                if is_final:
                    transcript_event = ExecutionEvent.transcript_final(execution_id, text)
                else:
                    transcript_event = ExecutionEvent.transcript_partial(execution_id, text)
                await self.event_hub.publish(transcript_event)
            except Exception as e:
                logger.debug(f"Error emitiendo evento de transcripción: {e}")
        
        try:
            await self.asr_provider.set_transcript_handler(_on_transcript)
            logger.debug(f"ASR: Transcript handler registrado a máquina de estados")
        except Exception as e:
            logger.error(f"ASR: Error registrando handler: {e}")
            return False, ""

        async def _fail_current_step(
            step_number: int,
            expected_text: str,
            actual_text: str | None,
            reason: str,
            reason_code: str,
            confidence: Decimal = Decimal("0.00"),
        ) -> None:
            """Persist and publish a terminal step failure before aborting flow."""
            await self._record_step_failure(
                execution_id=execution_id,
                call_sid=call_sid,
                step_number=step_number,
                expected_text=expected_text,
                actual_text=actual_text,
                reason=reason,
                reason_code=reason_code,
                confidence=confidence,
                execution_log_repo=execution_log_repo,
            )
        
        # 3. Bucle principal continuo
        all_passed = True
        last_dtmf_timestamp: float | None = None  # Track timestamp del último DTMF enviado
        grace_period_logged: bool = False  # Track si ya logeamos entrada a grace period
        try:
            while not state_machine.is_flow_complete():
                current_step = state_machine.get_current_step()
                if current_step is None:
                    break
                
                step_number = current_step.get("step", state_machine.state.current_step_index + 1)
                expected_text = current_step.get("listen", "")
                
                # 3a. Obtener audio chunks y enviarlos al ASR
                try:
                    chunk = await self.call_session_store.try_dequeue_audio(
                        call_sid, timeout_seconds=STREAM_POLL_SECONDS
                    )
                    if chunk:
                        await self.asr_provider.send_audio(chunk)
                except ValueError:
                    # Sesión cerrada
                    logger.warning(f"Step {step_number}: Call session ended before step completion")
                    await _fail_current_step(
                        step_number=step_number,
                        expected_text=expected_text,
                        actual_text=state_machine.get_full_text_buffer() or None,
                        reason="Call session ended before completing step",
                        reason_code="call_session_ended",
                    )
                    all_passed = False
                    break
                
                # 3b. Chequear si hay match con el step actual
                match_result = state_machine.check_for_step_match()
                if match_result:
                    logger.info(
                        f"Step {step_number}: ✓ MATCH DETECTED | matched_text='{match_result.matched_text}' | "
                        f"confidence={match_result.confidence}% | action={match_result.action_to_execute or 'None'}"
                    )
                    
                    # Emitir evento de step matched
                    try:
                        step_matched_event = ExecutionEvent.step_matched(
                            execution_id,
                            step_number,
                            match_result.matched_text,
                            float(match_result.confidence),
                        )
                        await self.event_hub.publish(step_matched_event)
                    except Exception as e:
                        logger.debug(f"Error emitiendo evento de step_matched: {e}")
                    
                    # 3b1. Ejecutar acción (DTMF) si aplica
                    if match_result.action_to_execute:
                        action_log, has_error = await self._execute_action(
                            call_sid, match_result.action_to_execute, step_number
                        )
                        if not has_error:
                            # Registrar timestamp de DTMF para grace period
                            last_dtmf_timestamp = time()
                            grace_period_logged = False  # Reset para loguear la próxima entrada a grace period
                        if has_error:
                            logger.error(f"Step {step_number}: DTMF execution failed: {action_log}")
                            await _fail_current_step(
                                step_number=step_number,
                                expected_text=expected_text,
                                actual_text=match_result.matched_text,
                                reason=action_log,
                                reason_code="dtmf_error",
                                confidence=match_result.confidence,
                            )
                            all_passed = False
                            break
                    else:
                        action_log = "No action (passive step)"
                        logger.info(f"Step {step_number}: Passive step (no action required)")
                    
                    # 3b2. Guardar log del step en BD
                    await self._log_step(
                        execution_id,
                        step_number,
                        current_step.get("listen", ""),
                        match_result.matched_text,
                        match_result.confidence,
                        action_log,
                        execution_log_repo=execution_log_repo,
                    )
                    
                    # 3b3. Avanzar al siguiente step
                    state_machine.advance_to_next_step(match_result.matched_text)
                    continue
                
                # 3c. Chequear relaciones entre transcripción actual y anterior
                current_full_text = state_machine.get_full_text_buffer()
                
                # 3c1. Detectar si el IVR está repitiendo el mismo menú (contenido se repite >= 50%)
                if current_full_text and len(current_full_text) > 10:  # Solo si hay suficiente texto
                    if state_machine.check_if_step_repeated(current_full_text, repeat_threshold=0.50):
                        # El IVR está repitiendo → ninguna opción hizo match durante el ciclo anterior
                        logger.warning(
                            f"Step {step_number}: ✗ REPETITION → No match found. "
                            f"IVR is repeating the menu. Expected: '{current_step.get('listen', '')}'"
                        )
                        await _fail_current_step(
                            step_number=step_number,
                            expected_text=expected_text,
                            actual_text=current_full_text,
                            reason="IVR repeated menu without matching expected step",
                            reason_code="menu_repetition",
                        )
                        all_passed = False
                        break

                # 3c2. Timeout por step para evitar loops infinitos cuando no existe match posible
                if state_machine.check_step_timeout():
                    elapsed = state_machine.get_elapsed_time_current_step()
                    best_ratio = state_machine.get_best_similarity_ratio()

                    # Fallback para pasos pasivos largos: permite continuar si hubo
                    # suficiente similitud al agotar timeout, evitando falsos negativos
                    # intermitentes por ASR en mensajes de bienvenida extensos.
                    expected_tokens = self._tokenize_for_similarity(expected_text)
                    is_passive_timeout_candidate = (
                        not current_step.get("action")
                        and len(expected_tokens) >= PASSIVE_TIMEOUT_FALLBACK_MIN_TOKENS
                        and best_ratio >= PASSIVE_TIMEOUT_FALLBACK_RATIO
                    )
                    if is_passive_timeout_candidate:
                        matched_excerpt, remaining_text = self._extract_matched_excerpt_and_remainder(
                            expected_text,
                            current_full_text or "",
                        )
                        consumed_text = matched_excerpt or current_full_text or ""
                        fallback_confidence = Decimal(str(best_ratio * 100)).quantize(Decimal("0.01"))
                        logger.warning(
                            f"Step {step_number}: Passive timeout fallback accepted | "
                            f"ratio={best_ratio:.2%} | elapsed={elapsed:.1f}s"
                        )

                        try:
                            step_matched_event = ExecutionEvent.step_matched(
                                execution_id,
                                step_number,
                                consumed_text,
                                float(fallback_confidence),
                            )
                            await self.event_hub.publish(step_matched_event)
                        except Exception as e:
                            logger.debug(f"Error emitiendo evento de step_matched en timeout fallback: {e}")

                        await self._log_step(
                            execution_id,
                            step_number,
                            expected_text,
                            consumed_text or None,
                            fallback_confidence,
                            (
                                "No action (passive step - timeout fallback accepted: "
                                f"{best_ratio:.2%})"
                            ),
                            execution_log_repo=execution_log_repo,
                        )
                        state_machine.advance_to_next_step(consumed_text, remaining_text or "")
                        continue

                    await _fail_current_step(
                        step_number=step_number,
                        expected_text=expected_text,
                        actual_text=current_full_text or None,
                        reason=(
                            f"Step timeout exceeded: {elapsed:.1f}s >= {STEP_TIMEOUT_SECONDS}s "
                            f"(best_ratio={best_ratio:.2%})"
                        ),
                        reason_code="step_timeout",
                        confidence=Decimal(str(best_ratio * 100)).quantize(Decimal("0.01")),
                    )
                    all_passed = False
                    break

                # 3c3. Detectar estancamiento: baja similitud sin mejoras por una ventana sostenida
                if state_machine.check_step_stagnation(
                    stagnation_seconds=STEP_STAGNATION_SECONDS,
                    max_ratio_without_progress=STEP_STAGNATION_MAX_RATIO,
                    min_silence_seconds=STEP_STAGNATION_MIN_SILENCE_SECONDS,
                ):
                    best_ratio = state_machine.get_best_similarity_ratio()
                    wait_without_progress = state_machine.get_seconds_since_similarity_improvement()
                    await _fail_current_step(
                        step_number=step_number,
                        expected_text=expected_text,
                        actual_text=current_full_text or None,
                        reason=(
                            f"Step stagnated: no similarity improvement for {wait_without_progress:.1f}s "
                            f"with best_ratio={best_ratio:.2%}"
                        ),
                        reason_code="step_stagnation",
                        confidence=Decimal(str(best_ratio * 100)).quantize(Decimal("0.01")),
                    )
                    all_passed = False
                    break

                
                # 3c4. EXTREME SILENCE CHECK - Cortar llamada si >15s sin audio/transcripción
                # Pero respetar grace period de 4s post-DTMF para transiciones normales
                silence_duration = state_machine.get_silence_duration()
                in_grace_period = False
                if last_dtmf_timestamp is not None:
                    time_since_dtmf = time() - last_dtmf_timestamp
                    if time_since_dtmf < GRACE_PERIOD_AFTER_DTMF_SECONDS:
                        in_grace_period = True
                        # Log solo una vez cuando se ENTRA al grace period, no en cada iteración
                        if not grace_period_logged:
                            logger.debug(
                                f"Step {step_number}: ✓ Grace period started (post-DTMF immunity: {GRACE_PERIOD_AFTER_DTMF_SECONDS}s)"
                            )
                            grace_period_logged = True
                    else:
                        # Grace period finalizó
                        if grace_period_logged:
                            logger.debug(
                                f"Step {step_number}: Grace period expired ({time_since_dtmf:.1f}s elapsed)"
                            )
                            grace_period_logged = False
                
                if not in_grace_period and state_machine.check_extreme_silence_timeout():
                    # Silencio extremo detectado - FAIL FAST y colgar
                    logger.critical(
                        f"Step {step_number}: ✗ EXTREME SILENCE ({silence_duration:.1f}s >= {EXTREME_SILENCE_THRESHOLD_SECONDS}s) - "
                        f"Terminating execution and call"
                    )
                    await _fail_current_step(
                        step_number=step_number,
                        expected_text=expected_text,
                        actual_text=current_full_text or None,
                        reason=f"Extreme caller silence: {silence_duration:.1f}s (threshold: {EXTREME_SILENCE_THRESHOLD_SECONDS}s)",
                        reason_code="extreme_silence",
                    )
                    
                    # Intentar colgar la llamada de inmediato
                    try:
                        await self.call_provider.hangup(call_sid)
                        logger.info(f"Step {step_number}: ✓ Call hung up due to extreme silence")
                    except Exception as hangup_err:
                        logger.warning(f"Step {step_number}: Could not hangup during extreme silence: {hangup_err}")
                    
                    all_passed = False
                    break
                
                # 3c5. Chequear silencio (informativo - no interrumpe la espera)
                silence_duration = state_machine.get_silence_duration()
                if silence_duration >= SILENCE_THRESHOLD_SECONDS and silence_duration < SILENCE_THRESHOLD_SECONDS + 0.1:
                    # Log una sola vez cuando cruza el umbral (evitar spam)
                    logger.debug(
                        f"Step {step_number}: Silence detected ({silence_duration:.1f}s) "
                        f"- continuing to listen for expected text..."
                    )
                
                # 3d. Permitir que otros tasks ejecuten
                await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.error(f"STATE MACHINE FLOW ERROR: {e}", exc_info=True)
            self._log_flow_error(
                "State machine error",
                level="error",
                error_type="flow",
                reason_code="state_machine_exception",
                execution_id=str(execution_id),
                call_sid=call_sid,
                error_category=classify_error_category(e),
                error_message=str(e),
            )
            all_passed = False

        if all_passed and not state_machine.is_flow_complete():
            logger.warning(
                "Flow marked as incomplete: not all steps were validated successfully. "
                "Forcing global FAILED status."
            )
            all_passed = False
        
        # 4. Finalizar y obtener transcript completo
        final_transcript = state_machine.finalize_and_get_full_transcript()
        logger.info(
            f"STATE MACHINE FLOW END | all_passed={all_passed} | transcript_length={len(final_transcript)} | "
            f"steps_processed={state_machine.state.current_step_index}/{len(flow_script)}"
        )
        
        return all_passed, final_transcript

    async def _process_single_step(
        self,
        execution_id: UUID,
        call_sid: str,
        step: dict,
        step_index: int,
        should_clear_queue: bool = True,
        execution_log_repo: IExecutionLogRepository | None = None,
    ) -> bool:
        """Procesa un único paso del test case (audio, transcripción, evaluación, acción y log). Retorna True si pasó."""
        step_number = step.get("step", step_index)
        expected_text = step.get("listen", "")
        action = step.get("action")

        execution_log_repo = execution_log_repo or self.execution_log_repo
        
        # === BEGIN STEP LOG ===
        logger.info(f"{'='*80}")
        logger.info(f"Step {step_number}: START | listening for: '{expected_text}' | action_required: {action}")
        logger.info(f"{'='*80}")
        
        # 1. Esperar audio y transcribir con early exit si hay partial match
        logger.debug(f"Step {step_number}: Waiting for transcription...")
        transcription_start = time()
        transcription, error_msg = await self._get_transcription(
            call_sid, step_number, expected_text, should_clear_queue
        )
        transcription_elapsed = time() - transcription_start
        
        if error_msg:
            # Fallo en el audio o transcripción
            logger.error(f"Step {step_number}: ✗ TRANSCRIPTION ERROR - {error_msg} (elapsed={transcription_elapsed:.2f}s)")
            await self._log_step(
                execution_id,
                step_number,
                expected_text,
                None,
                Decimal("0.00"),
                error_msg,
                execution_log_repo=execution_log_repo,
            )
            return False
        
        logger.debug(f"Step {step_number}: Transcription received in {transcription_elapsed:.2f}s: '{transcription}'")
            
        # 2. Evaluar similitud del texto
        logger.debug(f"Step {step_number}: Evaluating transcription similarity...")
        similarity, confidence, is_match = self._evaluate_transcription(expected_text, transcription)
        logger.info(f"Step {step_number}: MATCH EVALUATION | similarity={similarity:.0%} | confidence={confidence} | threshold={SIMILARITY_THRESHOLD:.0%} | result={'✓ PASS' if is_match else '✗ FAIL'}")
        
        if not is_match:
            logger.warning(f"Step {step_number}: ✗ TEXT MISMATCH | expected='{expected_text}' | transcribed='{transcription}'")
            await self._log_step(
                execution_id,
                step_number,
                expected_text,
                transcription,
                confidence,
                "Failed text match",
                execution_log_repo=execution_log_repo,
            )
            return False

        logger.info(f"Step {step_number}: ✓ TEXT MATCHED | confidence={confidence}%")

        # 3. Ejecutar acción (DTMF) si aplica
        if action:
            logger.info(f"Step {step_number}: DTMF ACTION REQUIRED | digits='{action}' | preparing to send...")
        
        action_taken, action_error = await self._execute_action(call_sid, action, step_number)
        
        if action_error:
            logger.error(f"Step {step_number}: ✗ ACTION FAILED | {action_taken}")
            await self._log_step(
                execution_id,
                step_number,
                expected_text,
                transcription,
                confidence,
                action_taken,
                execution_log_repo=execution_log_repo,
            )
            return False

        # 4. Guardar log exitoso
        logger.debug(f"Step {step_number}: Recording step log in database...")
        await self._log_step(
            execution_id,
            step_number,
            expected_text,
            transcription,
            confidence,
            action_taken,
            execution_log_repo=execution_log_repo,
        )
        logger.info(f"Step {step_number}: ✓ COMPLETED successfully | action={action_taken} | confidence={confidence}%")
        logger.info(f"{'='*80}")
        return True

    async def _get_transcription(
        self, call_sid: str, step_number: int, expected_text: str = "", should_clear_queue: bool = True
    ) -> tuple[str | None, str | None]:
        """Extrae audio en streaming y espera transcripción final con early exit on partial match.
        
        Implementa evaluación en tiempo real: si se detecta que la transcripción parcial/final
        cumple con el umbral de similitud, dispara un early exit para evitar la latencia de silencio.
        
        Retorna (transcripción, mensaje_de_error).
        """
        logger.debug(f"Step {step_number}: [ASR] Initializing audio capture | call_sid={call_sid} | expected_text='{expected_text}'")
        
        if should_clear_queue:
            # 1. Limpiar cola de audio de cualquier chunk residual del inicio de la llamada
            await self.call_session_store.clear_queue(call_sid)
            logger.debug(f"Step {step_number}: [ASR] Audio queue cleared")
        else:
            logger.info(f"Step {step_number}: [ASR] PRESERVING audio queue to capture speech during DTMF/wait times")
        
        transcript_parts: list[str] = []
        current_partial: str = ""
        transcript_final = asyncio.Event()
        early_match_found = False
        
        # Guardaremos el tiempo en el que se recibió el último fragmento de texto
        last_text_time = time()
        asr_connect_start = time()

        async def _on_transcript(text: str, is_final: bool, speech_final: bool = False) -> None:
            nonlocal current_partial, last_text_time, early_match_found
            
            # Si recibimos texto (sea final o parcial), actualizamos el last_text_time
            if text:
                last_text_time = time()
                
            if is_final:
                if text:
                    transcript_parts.append(text)
                current_partial = ""
                # Si Deepgram detecta que es el fin de la voz (endpointing), seteamos el final
                if speech_final:
                    transcript_final.set()
            else:
                if text:
                    current_partial = text
            
            # NOTA: Ya no evaluamos el early exit inmediatamente aquí.
            # Se evaluará en el loop principal cuando haya una pausa (EARLY_EXIT_SILENCE_SECONDS).

        try:
            # Si la conexión persistente no está activa (surgery fallback), la creamos.
            if not getattr(self.asr_provider, "_is_connected", False):
                logger.debug(f"Step {step_number}: [ASR] Conexión no activa, realizando conexión de emergencia...")
                await self.asr_provider.connect(
                    encoding="mulaw",
                    sample_rate=8000,
                    endpointing=int(SILENCE_THRESHOLD_SECONDS * 1000),
                )
                asr_connect_elapsed = time() - asr_connect_start
                logger.debug(f"Step {step_number}: [ASR] ✓ Connected in {asr_connect_elapsed:.3f}s")
            else:
                logger.debug(f"Step {step_number}: [ASR] Reutilizando conexión Deepgram persistente")

            await self.asr_provider.set_transcript_handler(_on_transcript)
            logger.debug(f"Step {step_number}: [ASR] Transcript handler registered")
        except Exception as e:
            logger.error(f"Step {step_number}: [ASR] ✗ Connect error: {e}")
            return None, f"ASR connect error: {str(e)[:255]}"

        start_time = time()
        last_audio_time = start_time
        got_audio = False

        try:
            while True:
                elapsed = time() - start_time
                if elapsed >= AUDIO_TIMEOUT_SECONDS:
                    logger.warning(
                        f"Step {step_number}: [ASR] timeout waiting for whole audio ({AUDIO_TIMEOUT_SECONDS}s)"
                    )
                    break

                # Esperar un chunk corto para permitir detectar silencio
                try:
                    chunk = await self.call_session_store.try_dequeue_audio(
                        call_sid, timeout_seconds=STREAM_POLL_SECONDS
                    )
                except ValueError as e:
                    # Call has been closed on Stream stop, o se eliminó la sesión.
                    logger.info(f"Step {step_number}: [ASR] call session ended while waiting audio: {e}")
                    break

                if chunk:
                    got_audio = True
                    # Solo actualizamos el tiempo de último audio si el chunk NO ES silencio (o lo asumimos siempre).
                    # Twilio manda chunks constantemente incluso si hay silencio. Por lo que "last_audio_time" 
                    # nunca se va a dar a menos que se use VAD local, o Deepgram nos avise de is_final.
                    # Deepgram endpointing es la mejor estrategia para el silencio.
                    last_audio_time = time()
                    await self.asr_provider.send_audio(chunk)

                # Evaluamos condiciones basadas en el tiempo transcurrido desde el último texto
                if got_audio:
                    time_since_last_text = time() - last_text_time
                    
                    # 1. === EARLY EXIT (Dual Strategy) ===
                    if expected_text and not early_match_found:
                        current_full_text = " ".join(transcript_parts) + (" " + current_partial if current_partial else "")
                        current_full_text = current_full_text.strip()
                        
                        if current_full_text:
                            # Evaluamos la transcripción actual en tiempo real
                            ratio, _, is_match = self._evaluate_transcription(
                                expected_text, 
                                current_full_text,
                                threshold=EARLY_EXIT_THRESHOLD
                            )
                            
                            # Estrategia A: Match perfecto o casi perfecto (>= 86%)
                            # Salimos inmediatamente para no robarnos el audio de la siguiente oración.
                            # NOTA: Deepgram a veces transcribe mal ("minivr" en vez de "mi ivr" -> 86.79% match)
                            if ratio >= 0.85:
                                logger.info(
                                    f"Step {step_number}: ✓ IMMEDIATE EARLY EXIT - match >= 85% ({ratio:.0%}) sin esperar silencio final. "
                                    f"Expected: '{expected_text}', Got: '{current_full_text}'"
                                )
                                early_match_found = True
                                break  # Salimos inmediatamente
                                
                            # Estrategia B: Match parcial (>= EARLY_EXIT_THRESHOLD) + Silencio
                            # Si no es perfecto, esperamos un poquito de silencio para asegurar que terminó la idea.
                            elif is_match and time_since_last_text >= EARLY_EXIT_SILENCE_SECONDS:
                                logger.info(
                                    f"Step {step_number}: ✓ EARLY EXIT CON SILENCIO - match >= {EARLY_EXIT_THRESHOLD:.0%} ({ratio:.0%}) AND {EARLY_EXIT_SILENCE_SECONDS}s of silence! "
                                    f"Expected: '{expected_text}', Got: '{current_full_text}'"
                                )
                                early_match_found = True
                                break  # Salimos inmediatamente
                    
                    # 2. === SILENCE TIMEOUT NORMAL ===
                    # Si pasaron muchos segundos desde el último fragmento de TEXTO, asumimos que hubo silencio
                    # absoluto largo o la persona dejó de hablar (Fallback de seguridad).
                    if time_since_last_text >= SILENCE_THRESHOLD_SECONDS + 3.0:
                        logger.debug(
                            f"Step {step_number}: [ASR] timeout de silence absoluto ({SILENCE_THRESHOLD_SECONDS + 3.0}s) tras texto de deepgram, finalizando step"
                        )
                        break

                # Si Deepgram nos indicó que la transcripción finalizó debido a que se identificó fin de habla (speech_final)
                if transcript_final.is_set():
                    logger.debug(f"Step {step_number}: [ASR] Deepgram detectó endpointing y finalizó.")
                    # Dar tiempo a atributos tardíos para llegar antes de cerrar
                    await asyncio.sleep(0.5)
                    break
        finally:
            # Nota: NO se desconecta en cada step. La conexión es persistente y se cierra al final del flujo.
            pass

        final_text = " ".join(transcript_parts)
        if not final_text and current_partial:
            final_text = current_partial

        if final_text:
            final_text = final_text.strip()
            if early_match_found:
                logger.info(
                    f"Step {step_number}: [ASR] ✓ transcribed (early exit) '{final_text}'"
                )
            else:
                logger.info(
                    f"Step {step_number}: [ASR] ✓ transcribed (normal timeout) '{final_text}'"
                )
            return final_text, None

        if not got_audio:
            logger.error(f"Step {step_number}: [ASR] ✗ Timeout waiting for audio")
            return None, "Timeout waiting for audio"

        logger.error(f"Step {step_number}: [ASR] ✗ No transcription received")
        return None, "No transcription received"

    def _evaluate_transcription(self, expected_text: str, transcription: str, threshold: float | None = None) -> tuple[float, Decimal, bool]:
        """Compara la transcripción con el texto esperado usando Sliding Window.
        
        Retorna (similitud, confidencia_decimal, es_acierto).
        
        Estrategia:
        1. Primero intenta un match directo (fast path): si el expected_text está exactamente en la transcripción
        2. Luego usa una ventana deslizante de palabras para encontrar la mejor coincidencia parcial
        3. Si la transcripción es más corta que lo esperado, compara todo de inicio a fin (fallback)
        
        Args:
            expected_text: Texto esperado a buscar
            transcription: Texto transcrito
            threshold: Umbral de similitud (0-1). Por defecto usa SIMILARITY_THRESHOLD. 
                      Usa EARLY_EXIT_THRESHOLD para evaluación en streaming.
        """
        if threshold is None:
            threshold = SIMILARITY_THRESHOLD

        exp_normalized = self._normalize_similarity_text(expected_text)
        trans_normalized = self._normalize_similarity_text(transcription)

        if not exp_normalized or not trans_normalized:
            return 0.0, Decimal("0.00"), False
        
        # === FAST PATH 1: Exact substring match ===
        if exp_normalized in trans_normalized:
            logger.debug(f"_evaluate_transcription: EXACT MATCH found. Expected: '{expected_text}' (len={len(expected_text)}) in Transcription: '{transcription}' (len={len(transcription)})")
            return 1.0, Decimal("100.00"), True
        
        # === SLIDING WINDOW APPROACH ===
        # Dividir en tokens normalizados para tolerar mejor ruido ASR y puntuación.
        words_exp = self._tokenize_for_similarity(expected_text)
        words_trans = self._tokenize_for_similarity(transcription)
        window_size = len(words_exp)

        if not words_exp or not words_trans:
            fallback_ratio = SequenceMatcher(None, exp_normalized, trans_normalized, autojunk=False).ratio()
            confidence = Decimal(str(fallback_ratio * 100)).quantize(Decimal("0.01"))
            return fallback_ratio, confidence, fallback_ratio >= threshold
        
        logger.debug(f"_evaluate_transcription: Using Sliding Window. Expected words={words_exp} (count={window_size}), Transcription words={words_trans} (count={len(words_trans)})")
        
        # Coverage global: mide qué tanto del expected aparece en orden, aunque haya texto extra.
        best_ratio = self._ordered_token_coverage(words_exp, words_trans)
        best_window_idx = -1
        best_metric = "global_ordered_coverage"
        
        # Slide over chunks of the closest size to expected_text
        if len(words_trans) >= window_size and window_size > 0:
            for i in range(len(words_trans) - window_size + 1):
                window_tokens = words_trans[i:i + window_size]
                window_text = " ".join(window_tokens)

                char_ratio = SequenceMatcher(None, exp_normalized, window_text, autojunk=False).ratio()
                token_ratio = SequenceMatcher(None, words_exp, window_tokens, autojunk=False).ratio()
                coverage_ratio = self._ordered_token_coverage(words_exp, window_tokens)
                ratio = max(char_ratio, token_ratio, coverage_ratio)

                logger.debug(
                    f"  Window[{i}]: ratio={ratio:.2%} "
                    f"(char={char_ratio:.2%}, token={token_ratio:.2%}, coverage={coverage_ratio:.2%})"
                )
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_window_idx = i
                    if ratio == coverage_ratio:
                        best_metric = "window_ordered_coverage"
                    elif ratio == token_ratio:
                        best_metric = "window_token_ratio"
                    else:
                        best_metric = "window_char_ratio"
        else:
            # Fallback if transcription is shorter than expected: full comparison
            logger.debug(f"_evaluate_transcription: Transcription shorter than expected, using full comparison fallback")
            full_char_ratio = SequenceMatcher(None, exp_normalized, trans_normalized, autojunk=False).ratio()
            full_token_ratio = SequenceMatcher(None, words_exp, words_trans, autojunk=False).ratio()
            full_coverage_ratio = self._ordered_token_coverage(words_exp, words_trans)
            best_ratio = max(full_char_ratio, full_token_ratio, full_coverage_ratio, best_ratio)
            best_metric = "full_fallback"
            logger.debug(
                f"  Full comparison ratio={best_ratio:.2%} "
                f"(char={full_char_ratio:.2%}, token={full_token_ratio:.2%}, coverage={full_coverage_ratio:.2%})"
            )

        if len(words_exp) >= 10:
            expected_unique_tokens = set(words_exp)
            candidate_unique_tokens = set(words_trans)
            unordered_coverage_ratio = len(expected_unique_tokens & candidate_unique_tokens) / len(expected_unique_tokens)
            if unordered_coverage_ratio > best_ratio:
                best_ratio = unordered_coverage_ratio
                best_metric = "unordered_token_coverage"
                logger.debug(
                    f"  Unordered coverage ratio={unordered_coverage_ratio:.2%} "
                    f"(unique_expected={len(expected_unique_tokens)}, unique_candidate={len(candidate_unique_tokens)})"
                )
        
        confidence = Decimal(str(best_ratio * 100)).quantize(Decimal("0.01"))
        is_match = best_ratio >= threshold
        
        logger.debug(
            f"_evaluate_transcription: FINAL RESULT - best_ratio={best_ratio:.2%}, confidence={confidence}, "
            f"is_match={is_match}, threshold={threshold:.0%}, metric={best_metric}, best_window={best_window_idx}"
        )
        
        return best_ratio, confidence, is_match

    def _normalize_similarity_text(self, text: str) -> str:
        """Normalize text for resilient ASR similarity comparison."""
        lowered = text.lower()
        normalized = unicodedata.normalize("NFKD", lowered)
        without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        cleaned = re.sub(r"[^a-z0-9\s]", " ", without_accents)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _tokenize_for_similarity(self, text: str) -> list[str]:
        """Tokenize normalized text and remove common stopwords."""
        normalized = self._normalize_similarity_text(text)
        if not normalized:
            return []
        return [token for token in normalized.split() if token not in SIMILARITY_STOPWORDS]

    def _ordered_token_coverage(self, expected_tokens: list[str], candidate_tokens: list[str]) -> float:
        """Compute ordered coverage: how much expected appears in order within candidate."""
        if not expected_tokens or not candidate_tokens:
            return 0.0

        match_idx = 0
        for token in candidate_tokens:
            if match_idx >= len(expected_tokens):
                break
            if token == expected_tokens[match_idx]:
                match_idx += 1

        return match_idx / len(expected_tokens)

    async def _execute_action(self, call_sid: str, action: str | None, step_number: int) -> tuple[str, bool]:
        """Ejecuta una acción como enviar DTMF. Retorna (log_accion, hay_error).
        
        Logs detallados para debugging de flujos DTMF y timing.
        """
        if not action:
            logger.debug(f"Step {step_number}: No action required (passive listening step)")
            return "No action (passive step)", False
            
        try:
            digits = str(action)
            logger.info(f"Step {step_number}: [DTMF] ═══════════════════════════════════════════════════════════════")
            logger.info(f"Step {step_number}: [DTMF] PREPARING TO SEND DTMF")
            logger.info(f"Step {step_number}: [DTMF] | digits: '{digits}'")
            logger.info(f"Step {step_number}: [DTMF] | call_sid: {call_sid}")
            logger.debug(f"Step {step_number}: [DTMF] Timestamp: {datetime.now(timezone.utc).isoformat()}")
            
            dtmf_start = time()
            await self.call_provider.send_dtmf(call_sid=call_sid, digits=digits)
            dtmf_elapsed = time() - dtmf_start
            
            action_taken = f"Sent DTMF: {digits}"
            logger.info(f"Step {step_number}: [DTMF] ✓ SUCCESSFULLY SENT")
            logger.info(f"Step {step_number}: [DTMF] | digits: '{digits}'")
            logger.info(f"Step {step_number}: [DTMF] | duration: {dtmf_elapsed:.3f}s")
            logger.info(f"Step {step_number}: [DTMF] | timestamp_sent: {datetime.now(timezone.utc).isoformat()}")
            logger.info(f"Step {step_number}: [DTMF] Waiting 0.5s for IVR to process tone...")
            
            # Pausa para que el proveedor y el IVR procesen los tonos antes de escuchar
            pause_start = time()
            await asyncio.sleep(0.5)
            pause_elapsed = time() - pause_start
            
            logger.info(f"Step {step_number}: [DTMF] ✓ POST-SEND PAUSE COMPLETE")
            logger.info(f"Step {step_number}: [DTMF] | pause_duration: {pause_elapsed:.3f}s")
            logger.info(f"Step {step_number}: [DTMF] | ready_for_next_step: {datetime.now(timezone.utc).isoformat()}")
            logger.info(f"Step {step_number}: [DTMF] ═══════════════════════════════════════════════════════════════")
            
            return action_taken, False
        except Exception as e:
            logger.error(f"Step {step_number}: [DTMF] ═══════════════════════════════════════════════════════════════")
            logger.error(f"Step {step_number}: [DTMF] ✗ FAILED TO SEND DTMF")
            logger.error(f"Step {step_number}: [DTMF] | digits: '{action}'")
            logger.error(f"Step {step_number}: [DTMF] | error: {str(e)}")
            logger.error(f"Step {step_number}: [DTMF] | timestamp: {datetime.now(timezone.utc).isoformat()}")
            logger.error(f"Step {step_number}: [DTMF] ═══════════════════════════════════════════════════════════════")
            return f"DTMF error: {sanitize_error_message(e)}", True

    async def _log_step(
        self,
        execution_id: UUID,
        step_number: int,
        expected_text: str,
        actual_transcription: str | None,
        confidence: Decimal,
        action_taken: str,
        execution_log_repo: IExecutionLogRepository | None = None,
    ):
        """Encapsula la creación del log en base de datos para cada paso.
        
        Logs de persistencia para debugging de la capa de datos.
        """
        execution_log_repo = execution_log_repo or self.execution_log_repo
        logger.debug(f"Step {step_number}: [DB] Creating execution log | exec_id={execution_id} | expected='{expected_text}' | actual='{actual_transcription}' | confidence={confidence} | action='{action_taken}'")
        
        log = ExecutionLogEntity(
            id=None,
            execution_id=execution_id,
            step_number=step_number,
            expected_text=expected_text,
            actual_transcription=actual_transcription,
            confidence_score=confidence,
            action_taken=action_taken,
            created_at=datetime.now(timezone.utc),
        )
        try:
            await execution_log_repo.create(log)
            logger.debug(f"Step {step_number}: [DB] ✓ Execution log created and persisted")
        except Exception as e:
            logger.error(f"Step {step_number}: [DB] ✗ Failed to persist execution log | error={str(e)}", exc_info=True)

    def _tokenize_actual_with_raw_index(self, text: str) -> list[tuple[str, int]]:
        """Tokenize a transcription while preserving the raw token position."""
        raw_tokens = text.split()
        tokens_with_index: list[tuple[str, int]] = []

        for raw_index, raw_token in enumerate(raw_tokens):
            normalized = self._normalize_similarity_text(raw_token)
            if not normalized:
                continue
            for token in normalized.split():
                if token in SIMILARITY_STOPWORDS:
                    continue
                tokens_with_index.append((token, raw_index))

        return tokens_with_index

    def _extract_matched_excerpt_and_remainder(
        self,
        expected_text: str,
        actual_transcription: str,
    ) -> tuple[str | None, str | None]:
        """Extract the best matching excerpt and the leftover transcript tail."""
        expected_clean = expected_text.strip()
        actual_clean = actual_transcription.strip()
        if not expected_clean or not actual_clean:
            return None, None

        lower_actual = actual_clean.lower()
        lower_expected = expected_clean.lower()
        literal_start = lower_actual.find(lower_expected)
        if literal_start != -1:
            literal_end = literal_start + len(expected_clean)
            excerpt = actual_clean[literal_start:literal_end].strip() or None
            remainder = actual_clean[literal_end:].strip() or None
            return excerpt, remainder

        expected_tokens = self._tokenize_for_similarity(expected_clean)
        actual_tokens_with_raw_index = self._tokenize_actual_with_raw_index(actual_clean)
        if not expected_tokens or not actual_tokens_with_raw_index:
            return None, None

        actual_tokens = [token for token, _ in actual_tokens_with_raw_index]
        raw_tokens = actual_clean.split()
        window_size = len(expected_tokens)

        best_ratio = 0.0
        best_window_start = 0
        best_window_end = 0

        if len(actual_tokens) >= window_size and window_size > 0:
            for idx in range(len(actual_tokens) - window_size + 1):
                candidate_tokens = actual_tokens[idx:idx + window_size]

                char_ratio = SequenceMatcher(
                    None,
                    " ".join(expected_tokens),
                    " ".join(candidate_tokens),
                    autojunk=False,
                ).ratio()
                token_ratio = SequenceMatcher(
                    None,
                    expected_tokens,
                    candidate_tokens,
                    autojunk=False,
                ).ratio()
                coverage_ratio = self._ordered_token_coverage(expected_tokens, candidate_tokens)
                ratio = max(char_ratio, token_ratio, coverage_ratio)

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_window_start = idx
                    best_window_end = idx + window_size
        else:
            char_ratio = SequenceMatcher(
                None,
                " ".join(expected_tokens),
                " ".join(actual_tokens),
                autojunk=False,
            ).ratio()
            token_ratio = SequenceMatcher(
                None,
                expected_tokens,
                actual_tokens,
                autojunk=False,
            ).ratio()
            coverage_ratio = self._ordered_token_coverage(expected_tokens, actual_tokens)
            best_ratio = max(char_ratio, token_ratio, coverage_ratio)
            best_window_start = 0
            best_window_end = len(actual_tokens)

        if best_ratio <= 0.0 or best_window_end <= best_window_start:
            return None, None

        raw_start = actual_tokens_with_raw_index[best_window_start][1]
        raw_end = actual_tokens_with_raw_index[best_window_end - 1][1]
        excerpt = " ".join(raw_tokens[raw_start:raw_end + 1]).strip() or None
        remainder = " ".join(raw_tokens[raw_end + 1:]).strip() or None
        return excerpt, remainder

    async def _record_step_failure(
        self,
        execution_id: UUID,
        call_sid: str,
        step_number: int,
        expected_text: str,
        actual_text: str | None,
        reason: str,
        reason_code: str,
        confidence: Decimal,
        execution_log_repo: IExecutionLogRepository,
    ) -> None:
        """Persist step failure details and emit realtime failure event."""
        self._log_flow_error(
            "Step failed",
            level="warning",
            error_type="flow",
            reason_code=reason_code,
            execution_id=str(execution_id),
            call_sid=call_sid,
            step_number=step_number,
            expected_text=expected_text,
            actual_text=actual_text,
            confidence=confidence,
            error_message=reason,
        )
        await self._log_step(
            execution_id,
            step_number,
            expected_text,
            actual_text,
            confidence,
            reason,
            execution_log_repo=execution_log_repo,
        )

        try:
            step_failed_event = ExecutionEvent.step_failed(
                execution_id,
                step_number,
                expected_text,
                actual_text,
                reason,
            )
            await self.event_hub.publish(step_failed_event)
        except Exception as e:
            logger.debug(f"Error emitiendo evento step_failed: {e}")

    def _log_flow_error(self, message: str, level: str = "error", **fields) -> None:
        """Log flow or provider errors with consistent key=value fields."""
        field_text = format_log_fields(fields)
        log_message = f"{message} | {field_text}" if field_text else message

        if level == "warning":
            logger.warning(log_message)
        elif level == "info":
            logger.info(log_message)
        else:
            logger.error(log_message)

    async def _monitor_audio_inactivity(self, call_sid: str) -> None:
        """Monitor de inactividad de audio que reconecta ASR si deja de llegar audio.
        
        Se ejecuta en paralelo durante todo el flujo. Si no hay audio chunks
        por más de 5 segundos, intenta reconectar ASR automáticamente.
        
        Args:
            call_sid: ID de la llamada a monitorear
        """
        AUDIO_INACTIVITY_THRESHOLD = 5.0  # segundos
        CHECK_INTERVAL = 1.0  # chequear cada segundo
        
        try:
            while True:
                await asyncio.sleep(CHECK_INTERVAL)
                
                # Obtener cuánto tiempo ha pasado sin audio
                seconds_since_audio = await self.call_session_store.get_seconds_since_last_audio(call_sid)
                
                if seconds_since_audio is None:
                    # Sesión no existe, terminar monitor
                    logger.debug(f"Audio monitor: Sesión {call_sid} no existe, terminando monitor")
                    break
                
                # Si han pasado más de 5 segundos sin audio, reconectar ASR
                if seconds_since_audio > AUDIO_INACTIVITY_THRESHOLD:
                    is_connected = getattr(self.asr_provider, "_is_connected", False)
                    if is_connected:
                        logger.warning(
                            f"Audio monitor: No hay audio por {seconds_since_audio:.1f}s "
                            f"(threshold={AUDIO_INACTIVITY_THRESHOLD}s). Reconectando ASR..."
                        )
                        
                        try:
                            # Desconectar la conexión vieja
                            await self.asr_provider.disconnect()
                            await asyncio.sleep(0.5)  # Pequeña pausa
                            
                            # Reconectar ASR
                            await self.asr_provider.connect(
                                encoding="mulaw",
                                sample_rate=8000,
                                endpointing=int(SILENCE_THRESHOLD_SECONDS * 1000),
                            )
                            logger.info(f"Audio monitor: ✅ ASR reconectado exitosamente")
                            
                            # Reset el timestamp de último audio
                            session = await self.call_session_store.get_session(call_sid)
                            if session:
                                session.last_audio_timestamp = datetime.now(timezone.utc)
                        
                        except Exception as e:
                            logger.error(f"Audio monitor: ✗ Error reconectando ASR: {e}")
                            # Continuar intentando en la siguiente iteración
        
        except asyncio.CancelledError:
            logger.debug(f"Audio monitor: Detenido para llamada {call_sid}")
        except Exception as e:
            logger.error(f"Audio monitor: Error inesperado: {e}", exc_info=True)

    async def _finalize_execution(
        self,
        execution_id: UUID,
        call_sid: str,
        start_time: float,
        all_passed: bool,
        test_execution_repo: ITestExecutionRepository | None = None,
    ):
        """Actualiza el estado final de la ejecución de prueba y cuelga la llamada.
        
        Logs de finalización y status para visibilidad del flujo completo.
        """
        test_execution_repo = test_execution_repo or self.test_execution_repo
        duration = int(time() - start_time)
        final_status = "PASSED" if all_passed else "FAILED"

        logger.info(f"FINALIZE EXECUTION | execution_id={execution_id} | status={final_status} | duration={duration}s")
        
        try:
            await test_execution_repo.update_status(
                execution_id,
                status=final_status,
                duration_seconds=duration,
            )
            logger.info(f"FINALIZE EXECUTION | ✓ Status updated in DB | status={final_status}")
            
            # Emitir evento de finalización
            try:
                finish_event = ExecutionEvent.execution_finished(
                    execution_id,
                    final_status,
                    duration,
                )
                await self.event_hub.publish(finish_event)
                # Allow time for events to be delivered to subscribers
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"FINALIZE EXECUTION | Error publicando execution_finished: {e}")
                
        except Exception as e:
            logger.error(f"FINALIZE EXECUTION | ✗ Failed to update status | error={str(e)}", exc_info=True)
            
            # Emitir evento de error con mensaje filtrado
            try:
                # Log completo con detalle técnico para telemetry
                logger.error(
                    f"Finalize execution error for {execution_id}",
                    exc_info=True,
                    extra={
                        "execution_id": str(execution_id),
                        "raw_error": str(e),
                    }
                )
                
                # Emitir mensaje filtrado y amigable al WebSocket
                friendly_message = get_user_friendly_error_message(e)
                error_event = ExecutionEvent.execution_error(
                    execution_id,
                    friendly_message,
                    duration,
                )
                await self.event_hub.publish(error_event)
                # Allow time for events to be delivered to subscribers
                await asyncio.sleep(0.1)
            except Exception as e2:
                logger.error(f"FINALIZE EXECUTION | Error publicando execution_error: {e2}")
        
        try:
            await self.call_provider.hangup(call_sid)
            logger.info(f"FINALIZE EXECUTION | ✓ Call hung up | call_sid={call_sid}")
        except Exception as e:
            logger.warning(f"FINALIZE EXECUTION | ✗ Error hanging up call | error={str(e)}")
        
        # Limpiar sesión explícitamente después de hangup
        try:
            await self.call_session_store.close_session(call_sid)
            logger.info(f"FINALIZE EXECUTION | ✓ Session cleaned up | call_sid={call_sid}")
        except Exception as e:
            logger.warning(f"FINALIZE EXECUTION | ✗ Error closing session | error={str(e)}")

