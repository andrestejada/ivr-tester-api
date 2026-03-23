"""Use case para ejecutar un test case — orquestación de llamadas y pasos."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from time import time
from uuid import UUID
from typing import Callable

from src.domain.entities.execution_log import ExecutionLogEntity
from src.domain.entities.test_case import TestCaseEntity
from src.domain.entities.test_execution import TestExecutionEntity
from src.domain.ports.asr_provider import IASRProvider
from src.domain.ports.call_provider import ICallProvider
from src.domain.repositories.execution_log_repository import IExecutionLogRepository
from src.domain.repositories.test_case_repository import ITestCaseRepository
from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.application.exceptions import NotFoundError
from src.infrastructure.call_session_store import CallSessionStore
from src.infrastructure.database.uow import UnitOfWork
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)

# Constantes
AUDIO_TIMEOUT_SECONDS = 10.0
SILENCE_TIMEOUT_SECONDS = 3.0
STREAM_POLL_SECONDS = 0.5
SIMILARITY_THRESHOLD = 0.80  # 80%


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
            uow_factory: Factory para UnitOfWork en background
        """
        self.test_case_repo = test_case_repo
        self.test_execution_repo = test_execution_repo
        self.execution_log_repo = execution_log_repo
        self.call_provider = call_provider
        self.asr_provider = asr_provider
        self.call_session_store = call_session_store
        self.uow_factory = uow_factory

    async def execute(
        self, test_case_id: UUID, phone_number: str, webhook_url: str
    ) -> TestExecutionEntity:
        """Síncronamente crea la ejecución y lanza el proceso en background.
        
        Retorna la entidad RUNNING inmediatamente.
        """
        logger.info(f"Starting test case execution setup: {test_case_id}")
        
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
        # 1. Iniciar llamada
        try:
            call_session = await self.call_provider.initiate_call(
                phone_number=phone_number,
                webhook_url=webhook_url,
            )
            execution.provider_call_sid = call_session.call_sid
            logger.info(f"Call initiated: {call_session.call_sid}")
        except Exception as e:
            logger.error(f"Error initiating call: {e}")
            duration = int(time() - start_time)
            try:
                await test_execution_repo.update_status(
                    execution.id,
                    status="ERROR",
                    duration_seconds=duration,
                )
            except Exception as e2:
                logger.error(
                    f"Failed to update execution {execution.id} status to ERROR after initiate_call failure: {e2}"
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
                raise TimeoutError("Call was not answered or webhook was not received in time.")
            
            logger.info("Call answered and session active. Beginning step execution.")

            # 3. Bucle por los pasos
            all_passed = True
            for step_index, step in enumerate(test_case.flow_script, start=1):
                try:
                    passed = await self._process_single_step(
                        execution_id=execution.id,
                        call_sid=call_session.call_sid,
                        step=step,
                        step_index=step_index,
                        execution_log_repo=execution_log_repo,
                    )
                    if not passed:
                        all_passed = False
                        break
                except Exception as e:
                    logger.error(
                        f"Unexpected error processing step {step_index} in execution {execution.id}: {e}",
                        exc_info=True,
                    )
                    await test_execution_repo.update_status(
                        execution.id,
                        status="ERROR",
                        duration_seconds=int(time() - start_time),
                    )
                    # Intentar colgar en caso de error crítico
                    try:
                        await self.call_provider.hangup(call_session.call_sid)
                    except Exception:
                        pass
                    return

            # 3. Finalizar ejecución y colgar llamada
            await self._finalize_execution(
                execution.id,
                call_session.call_sid,
                start_time,
                all_passed,
                test_execution_repo=test_execution_repo,
            )

        except Exception as e:
            logger.error(f"Execution error general: {e}", exc_info=True)
            # Intentamos actualizar estado en caso de error no controlado
            try:
                await test_execution_repo.update_status(
                    execution.id,
                    status="ERROR",
                    duration_seconds=int(time() - start_time),
                )
            except Exception as e2:
                logger.error(f"Could not update status after background error: {e2}")

    async def _process_single_step(
        self,
        execution_id: UUID,
        call_sid: str,
        step: dict,
        step_index: int,
        execution_log_repo: IExecutionLogRepository | None = None,
    ) -> bool:
        """Procesa un único paso del test case (audio, transcripción, evaluación, acción y log). Retorna True si pasó."""
        step_number = step.get("step", step_index)
        expected_text = step.get("listen", "")
        action = step.get("action")

        execution_log_repo = execution_log_repo or self.execution_log_repo
        
        logger.info(f"Step {step_number}: listening for '{expected_text}'")
        
        # 1. Esperar audio y transcribir
        transcription, error_msg = await self._get_transcription(call_sid, step_number)
        if error_msg:
            # Fallo en el audio o transcripción
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
            
        # 2. Evaluar similitud del texto
        similarity, confidence, is_match = self._evaluate_transcription(expected_text, transcription)
        logger.info(f"Step {step_number}: similarity={similarity:.0%} (threshold={SIMILARITY_THRESHOLD:.0%})")
        if not is_match:
            logger.warning(f"Step {step_number}: text mismatch (expected '{expected_text}', got '{transcription}')")
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

        # 3. Ejecutar acción (DTMF) si aplica
        action_taken, action_error = await self._execute_action(call_sid, action, step_number)
        if action_error:
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
        await self._log_step(
            execution_id,
            step_number,
            expected_text,
            transcription,
            confidence,
            action_taken,
            execution_log_repo=execution_log_repo,
        )
        return True

    async def _get_transcription(self, call_sid: str, step_number: int) -> tuple[str | None, str | None]:
        """Extrae audio en streaming y espera transcripción final.
        
        Retorna (transcripción, mensaje_de_error).
        """
        transcript_text: dict[str, str] = {"text": ""}
        transcript_final = asyncio.Event()

        async def _on_transcript(text: str, is_final: bool) -> None:
            if text:
                transcript_text["text"] = text
            if is_final:
                transcript_final.set()

        try:
            await self.asr_provider.connect(
                encoding="mulaw",
                sample_rate=8000,
                endpointing=int(SILENCE_TIMEOUT_SECONDS * 1000),
            )
            await self.asr_provider.set_transcript_handler(_on_transcript)
        except Exception as e:
            logger.error(f"Step {step_number}: ASR connect error: {e}")
            return None, f"ASR connect error: {str(e)[:255]}"

        start_time = time()
        last_audio_time = start_time
        got_audio = False

        try:
            while True:
                elapsed = time() - start_time
                if elapsed >= AUDIO_TIMEOUT_SECONDS:
                    logger.error(
                        f"Step {step_number}: timeout waiting for audio ({AUDIO_TIMEOUT_SECONDS}s)"
                    )
                    break

                # Esperar un chunk corto para permitir detectar silencio
                try:
                    chunk = await self.call_session_store.try_dequeue_audio(
                        call_sid, timeout_seconds=STREAM_POLL_SECONDS
                    )
                except ValueError as e:
                    logger.error(f"Step {step_number}: audio queue error: {e}")
                    return None, "Audio queue error"

                if chunk:
                    got_audio = True
                    last_audio_time = time()
                    await self.asr_provider.send_audio(chunk)

                if transcript_final.is_set():
                    break

                # Si ya hubo audio, y pasaron N segundos sin chunks, asumimos fin del segmento
                if got_audio and (time() - last_audio_time) >= SILENCE_TIMEOUT_SECONDS:
                    break
        finally:
            try:
                await self.asr_provider.disconnect()
            except Exception:
                pass

        if transcript_text["text"]:
            logger.info(
                f"Step {step_number}: transcribed '{transcript_text['text']}'"
            )
            return transcript_text["text"], None

        if not got_audio:
            return None, "Timeout waiting for audio"

        return None, "No transcription received"

    def _evaluate_transcription(self, expected_text: str, transcription: str) -> tuple[float, Decimal, bool]:
        """Compara la transcripción con el texto esperado. Retorna (similitud, confidencia_decimal, es_acierto)."""
        similarity = SequenceMatcher(
            None, expected_text.lower(), transcription.lower()
        ).ratio()
        confidence = Decimal(str(similarity * 100)).quantize(Decimal("0.01"))
        is_match = similarity >= SIMILARITY_THRESHOLD
        return similarity, confidence, is_match

    async def _execute_action(self, call_sid: str, action: str | None, step_number: int) -> tuple[str, bool]:
        """Ejecuta una acción como enviar DTMF. Retorna (log_accion, hay_error)."""
        if not action:
            return "No action (passive step)", False
            
        try:
            digits = str(action)
            await self.call_provider.send_dtmf(call_sid=call_sid, digits=digits)
            action_taken = f"Sent DTMF: {digits}"
            logger.info(f"Step {step_number}: {action_taken}")
            
            # Pausa para que el proveedor y el IVR estilicen los tonos antes de escuchar
            await asyncio.sleep(0.5)
            return action_taken, False
        except Exception as e:
            logger.error(f"Step {step_number}: DTMF error: {e}")
            return f"DTMF error: {str(e)[:255]}", True

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
        """Encapsula la creación del log en base de datos para cada paso."""
        execution_log_repo = execution_log_repo or self.execution_log_repo
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
        await execution_log_repo.create(log)

    async def _finalize_execution(
        self,
        execution_id: UUID,
        call_sid: str,
        start_time: float,
        all_passed: bool,
        test_execution_repo: ITestExecutionRepository | None = None,
    ):
        """Actualiza el estado final de la ejecución de prueba y cuelga la llamada."""
        test_execution_repo = test_execution_repo or self.test_execution_repo
        duration = int(time() - start_time)
        final_status = "PASSED" if all_passed else "FAILED"

        await test_execution_repo.update_status(
            execution_id,
            status=final_status,
            duration_seconds=duration,
        )
        logger.info(f"Execution completed: {execution_id}, status={final_status}, duration={duration}s")
        
        try:
            await self.call_provider.hangup(call_sid)
            logger.info(f"Call hung up: {call_sid}")
        except Exception as e:
            logger.warning(f"Error hanging up call: {e}")

