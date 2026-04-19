"""Use case for retrieving complete test execution details with forensic logs."""

import re
import unicodedata
from difflib import SequenceMatcher
from uuid import UUID

from src.application.dtos.test_execution_details import (
    ExecutionLogResponse,
    TestCaseDetailResponse,
    TestExecutionDetailsResponse,
)
from src.domain.repositories.test_execution_repository import ITestExecutionRepository

# Stopwords comunes para robustecer la extracción de match en frases largas.
SIMILARITY_STOPWORDS = {
    "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "durante",
    "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "es", "esa", "ese",
    "esta", "este", "esto", "ha", "hasta", "la", "las", "le", "les", "lo", "los",
    "mas", "mi", "no", "o", "para", "pero", "por", "que", "se", "ser", "si",
    "sin", "su", "sus", "te", "tu", "un", "una", "uno", "y",
}


class GetTestExecutionDetailsUseCase:
    """Use case para obtener los detalles completos de una ejecución.
    
    Retorna la ejecución junto con:
    - TestCase asociado
    - IVRArchitecture del TestCase
    - Todos los logs de ejecución ordenados por step_number
    """

    def __init__(self, repository: ITestExecutionRepository):
        self.repository = repository

    def _normalize_similarity_text(self, text: str) -> str:
        """Normalize text for resilient similarity comparison."""
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

    def _tokenize_actual_with_raw_index(self, text: str) -> list[tuple[str, int]]:
        """Tokenize transcription while preserving each token's raw position."""
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

    def _is_failed_step_action(self, action_taken: str | None) -> bool:
        """Best-effort classification of terminal step failures based on action log."""
        if not action_taken:
            return False

        if action_taken.startswith("Sent DTMF:"):
            return False

        if action_taken.startswith("No action (passive step"):
            return False

        failure_patterns = (
            "Failed text match",
            "Timeout waiting for audio",
            "No transcription received",
            "Call session ended before completing step",
            "IVR repeated menu without matching expected step",
        )
        if action_taken in failure_patterns:
            return True

        lowered = action_taken.lower()
        return (
            action_taken.startswith("DTMF error:")
            or action_taken.startswith("ASR connect error:")
            or action_taken.startswith("Step timeout exceeded:")
            or action_taken.startswith("Step stagnated:")
            or action_taken.startswith("Extreme caller silence:")
            or "error" in lowered
            or "failed" in lowered
            or "timeout" in lowered
            or "stagnated" in lowered
            or "silence" in lowered
        )

    def _extract_matched_excerpt(
        self,
        expected_text: str | None,
        actual_transcription: str | None,
        action_taken: str | None,
    ) -> str | None:
        """Extract the best matching excerpt for successful or non-failed steps."""
        if self._is_failed_step_action(action_taken):
            return None

        if not expected_text or not actual_transcription:
            return None

        expected_clean = expected_text.strip()
        actual_clean = actual_transcription.strip()
        if not expected_clean or not actual_clean:
            return None

        # Fast path for contiguous literal matches.
        lower_actual = actual_clean.lower()
        lower_expected = expected_clean.lower()
        literal_start = lower_actual.find(lower_expected)
        if literal_start != -1:
            literal_end = literal_start + len(expected_clean)
            return actual_clean[literal_start:literal_end].strip() or None

        expected_tokens = self._tokenize_for_similarity(expected_clean)
        actual_tokens_with_raw_index = self._tokenize_actual_with_raw_index(actual_clean)
        if not expected_tokens or not actual_tokens_with_raw_index:
            return None

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
            return None

        raw_start = actual_tokens_with_raw_index[best_window_start][1]
        raw_end = actual_tokens_with_raw_index[best_window_end - 1][1]
        excerpt = " ".join(raw_tokens[raw_start:raw_end + 1]).strip()
        return excerpt or None

    async def execute(self, execution_id: UUID) -> TestExecutionDetailsResponse:
        """Ejecuta la obtención de detalles completos.

        Args:
            execution_id: ID de la ejecución a analizar.

        Returns:
            TestExecutionDetailsResponse con toda la información anidada.
            
        Raises:
            NotFoundError: Si la ejecución no existe.
        """
        # Obtiene la ejecución con todas las relaciones precargadas
        execution_model = await self.repository.get_by_id_with_details(execution_id)

        ordered_logs = sorted(execution_model.logs, key=lambda log: log.step_number)
        mapped_logs: list[ExecutionLogResponse] = []
        for log in ordered_logs:
            mapped_logs.append(
                ExecutionLogResponse(
                    id=log.id,
                    execution_id=log.execution_id,
                    step_number=log.step_number,
                    expected_text=log.expected_text,
                    actual_transcription=log.actual_transcription,
                    matched_excerpt=self._extract_matched_excerpt(
                        expected_text=log.expected_text,
                        actual_transcription=log.actual_transcription,
                        action_taken=log.action_taken,
                    ),
                    confidence_score=log.confidence_score,
                    action_taken=log.action_taken,
                    created_at=log.created_at,
                )
            )

        return TestExecutionDetailsResponse(
            id=execution_model.id,
            test_case_id=execution_model.test_case_id,
            status=execution_model.status,
            duration_seconds=execution_model.duration_seconds,
            provider_call_sid=execution_model.provider_call_sid,
            full_call_transcript=execution_model.full_call_transcript,
            executed_at=execution_model.executed_at,
            test_case=TestCaseDetailResponse.model_validate(execution_model.test_case),
            logs=mapped_logs,
        )
