"""Use case para ejecutar un test case — orquestación de llamadas y pasos."""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from time import time
from uuid import UUID

from src.domain.entities.execution_log import ExecutionLogEntity
from src.domain.entities.test_case import TestCaseEntity
from src.domain.entities.test_execution import TestExecutionEntity
from src.domain.ports.asr_provider import IASRProvider
from src.domain.ports.call_provider import ICallProvider
from src.domain.repositories.execution_log_repository import IExecutionLogRepository
from src.domain.repositories.test_case_repository import ITestCaseRepository
from src.domain.repositories.test_execution_repository import ITestExecutionRepository
from src.infrastructure.call_session_store import CallSessionStore

logger = logging.getLogger(__name__)

# Constantes
AUDIO_TIMEOUT_SECONDS = 10.0
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
    ) -> None:
        """Inicializa el use case con dependencias.
        
        Args:
            test_case_repo: Repositorio de test cases
            test_execution_repo: Repositorio de ejecuciones
            execution_log_repo: Repositorio de logs de steps
            call_provider: Proveedor de telefonía (Twilio)
            asr_provider: Proveedor de transcripción (Deepgram, etc)
            call_session_store: Store de sesiones activas
        """
        self.test_case_repo = test_case_repo
        self.test_execution_repo = test_execution_repo
        self.execution_log_repo = execution_log_repo
        self.call_provider = call_provider
        self.asr_provider = asr_provider
        self.call_session_store = call_session_store

    async def execute(
        self, test_case_id: UUID, phone_number: str, webhook_url: str
    ) -> TestExecutionEntity:
        """Síncronamente crea la ejecución y lanza el proceso en background.
        
        Retorna la entidad RUNNING inmediatamente.
        """
        logger.info(f"Starting test case execution setup: {test_case_id}")
        
        # 1. Crear ejecución inicial sincrónicamente para devolverla al HTTP router
        execution = await self.test_execution_repo.create(
            test_case_id=test_case_id,
            status="RUNNING",
            provider_call_sid=None,
        )
        logger.info(f"Execution created: {execution.id}")
        
        # 2. Obtener test case
        test_case = await self.test_case_repo.get_by_id(test_case_id)
        
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
        """Lógica principal de orquestación en background."""
        start_time = time()
        logger.info(f"Background processing started for execution: {execution.id}")
        
        try:
            # 1. Iniciar llamada
            call_session = await self._initiate_call(execution, phone_number, webhook_url, start_time)
            if not call_session:
                return  # Falló la llamada, terminamos ejecución (estado ya actualizado en el log)
            
            # 2. Bucle por los pasos
            all_passed = True
            for step_index, step in enumerate(test_case.flow_script, start=1):
                passed = await self._process_single_step(
                    execution_id=execution.id,
                    call_sid=call_session.call_sid,
                    step=step,
                    step_index=step_index,
                )
                if not passed:
                    all_passed = False
                    break
            
            # 3. Finalizar ejecución y colgar llamada
            await self._finalize_execution(execution.id, call_session.call_sid, start_time, all_passed)
        
        except Exception as e:
            logger.error(f"Execution error general: {e}", exc_info=True)
            raise

    async def _initiate_call(self, execution: TestExecutionEntity, phone_number: str, webhook_url: str, start_time: float):
        """Intenta iniciar la llamada y actualiza el estado en caso de error."""
        try:
            call_session = await self.call_provider.initiate_call(
                phone_number=phone_number,
                webhook_url=webhook_url,
            )
            execution.provider_call_sid = call_session.call_sid
            logger.info(f"Call initiated: {call_session.call_sid}")
            return call_session
        except Exception as e:
            logger.error(f"Error initiating call: {e}")
            duration = int(time() - start_time)
            await self.test_execution_repo.update_status(
                execution.id,
                status="ERROR",
                duration_seconds=duration,
            )
            return None

    async def _process_single_step(self, execution_id: UUID, call_sid: str, step: dict, step_index: int) -> bool:
        """Procesa un único paso del test case (audio, transcripción, evaluación, acción y log). Retorna True si pasó."""
        step_number = step.get("step", step_index)
        expected_text = step.get("listen", "")
        action = step.get("action")
        
        logger.info(f"Step {step_number}: listening for '{expected_text}'")
        
        # 1. Esperar audio y transcribir
        transcription, error_msg = await self._get_transcription(call_sid, step_number)
        if error_msg:
            # Fallo en el audio o transcripción
            await self._log_step(execution_id, step_number, expected_text, None, Decimal("0.00"), error_msg)
            return False
            
        # 2. Evaluar similitud del texto
        similarity, confidence, is_match = self._evaluate_transcription(expected_text, transcription)
        logger.info(f"Step {step_number}: similarity={similarity:.0%} (threshold={SIMILARITY_THRESHOLD:.0%})")
        if not is_match:
            logger.warning(f"Step {step_number}: text mismatch (expected '{expected_text}', got '{transcription}')")
            await self._log_step(execution_id, step_number, expected_text, transcription, confidence, "Failed text match")
            return False

        # 3. Ejecutar acción (DTMF) si aplica
        action_taken, action_error = await self._execute_action(call_sid, action, step_number)
        if action_error:
            await self._log_step(execution_id, step_number, expected_text, transcription, confidence, action_taken)
            return False

        # 4. Guardar log exitoso
        await self._log_step(execution_id, step_number, expected_text, transcription, confidence, action_taken)
        return True

    async def _get_transcription(self, call_sid: str, step_number: int) -> tuple[str | None, str | None]:
        """Extrae el audio y lo transcribe. Retorna (transcripción, mensaje_de_error)."""
        try:
            audio_bytes = await self.call_session_store.dequeue_audio(
                call_sid, timeout_seconds=AUDIO_TIMEOUT_SECONDS
            )
        except TimeoutError:
            logger.error(f"Step {step_number}: timeout waiting for audio ({AUDIO_TIMEOUT_SECONDS}s)")
            return None, "Timeout waiting for audio"

        try:
            transcription = await self.asr_provider.transcribe(audio_bytes)
            logger.info(f"Step {step_number}: transcribed '{transcription}'")
            return transcription, None
        except Exception as e:
            logger.error(f"Step {step_number}: transcription error: {e}")
            return None, f"Transcription error: {str(e)[:255]}"

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
        self, execution_id: UUID, step_number: int, expected_text: str, 
        actual_transcription: str | None, confidence: Decimal, action_taken: str
    ):
        """Encapsula la creación del log en base de datos para cada paso."""
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
        await self.execution_log_repo.create(log)

    async def _finalize_execution(self, execution_id: UUID, call_sid: str, start_time: float, all_passed: bool):
        """Actualiza el estado final de la ejecución de prueba y cuelga la llamada."""
        duration = int(time() - start_time)
        final_status = "PASSED" if all_passed else "FAILED"
        
        await self.test_execution_repo.update_status(
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
