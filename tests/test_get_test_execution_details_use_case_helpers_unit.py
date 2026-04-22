"""Additional unit tests for GetTestExecutionDetailsUseCase helper branches."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.application.use_cases.get_test_execution_details_use_case import (
    GetTestExecutionDetailsUseCase,
)


@pytest.fixture
def use_case() -> GetTestExecutionDetailsUseCase:
    return GetTestExecutionDetailsUseCase(repository=AsyncMock())


class TestGetExecutionDetailsHelperMethods:
    @pytest.mark.parametrize(
        "action_taken, expected",
        [
            (None, False),
            ("Sent DTMF: 1", False),
            ("No action (passive step)", False),
            ("Failed text match", True),
            ("DTMF error: invalid digit", True),
            ("ASR connect error: network timeout", True),
            ("Step timeout exceeded: 31.0s", True),
            ("Step stagnated: no progress", True),
            ("Extreme caller silence: 18.0s", True),
            ("unexpected ERROR from provider", True),
        ],
    )
    def test_is_failed_step_action_classification(
        self,
        use_case: GetTestExecutionDetailsUseCase,
        action_taken: str | None,
        expected: bool,
    ) -> None:
        assert use_case._is_failed_step_action(action_taken) is expected

    def test_tokenize_actual_with_raw_index_ignores_stopwords_and_keeps_raw_positions(
        self, use_case: GetTestExecutionDetailsUseCase
    ) -> None:
        tokens = use_case._tokenize_actual_with_raw_index(
            "Hola, y adios menu principal"
        )

        assert tokens == [("hola", 0), ("adios", 2), ("menu", 3), ("principal", 4)]

    def test_extract_matched_excerpt_returns_none_for_failed_action(
        self, use_case: GetTestExecutionDetailsUseCase
    ) -> None:
        result = use_case._extract_matched_excerpt(
            expected_text="bienvenido al sistema",
            actual_transcription="bienvenido al sistema de ventas",
            action_taken="Failed text match",
        )

        assert result is None

    def test_extract_matched_excerpt_returns_none_for_empty_payloads(
        self, use_case: GetTestExecutionDetailsUseCase
    ) -> None:
        assert (
            use_case._extract_matched_excerpt(
                expected_text=None,
                actual_transcription="texto",
                action_taken=None,
            )
            is None
        )
        assert (
            use_case._extract_matched_excerpt(
                expected_text="texto",
                actual_transcription="   ",
                action_taken=None,
            )
            is None
        )

    def test_extract_matched_excerpt_prefers_literal_contiguous_match(
        self, use_case: GetTestExecutionDetailsUseCase
    ) -> None:
        result = use_case._extract_matched_excerpt(
            expected_text="menu principal",
            actual_transcription="Hola MENU principal de ventas",
            action_taken="No action (passive step)",
        )

        assert result == "MENU principal"

    def test_extract_matched_excerpt_uses_token_window_when_literal_not_found(
        self, use_case: GetTestExecutionDetailsUseCase
    ) -> None:
        result = use_case._extract_matched_excerpt(
            expected_text="nuestro menu ha cambiado por favor escuche atentamente las opciones",
            actual_transcription=(
                "usuario estimado nuestro menu cambiado por favor que "
                "escuche atentamente opciones adicionales"
            ),
            action_taken="No action (passive step)",
        )

        assert result is not None
        assert "nuestro menu" in result
        assert "escuche atentamente" in result

    def test_extract_matched_excerpt_handles_short_actual_transcript_branch(
        self, use_case: GetTestExecutionDetailsUseCase
    ) -> None:
        result = use_case._extract_matched_excerpt(
            expected_text="hola mundo grande",
            actual_transcription="hola",
            action_taken=None,
        )

        assert result == "hola"

    def test_extract_matched_excerpt_returns_none_when_similarity_is_zero(
        self, use_case: GetTestExecutionDetailsUseCase
    ) -> None:
        result = use_case._extract_matched_excerpt(
            expected_text="abc",
            actual_transcription="xyz",
            action_taken=None,
        )

        assert result is None


class TestGetExecutionDetailsExecuteMethod:
    @pytest.mark.asyncio
    async def test_execute_sorts_logs_and_maps_matched_excerpt(self) -> None:
        repository = AsyncMock()
        use_case = GetTestExecutionDetailsUseCase(repository=repository)

        architecture = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440310"),
            user_id=UUID("550e8400-e29b-41d4-a716-446655440311"),
            name="Arch",
            phone_number="+12025550100",
            provider="twilio",
            description="desc",
            created_at=datetime(2025, 1, 1, 10, 0, 0),
        )
        test_case = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440312"),
            ivr_architecture_id=architecture.id,
            name="Case",
            flow_script=[{"step": 1, "listen": "menu principal", "action": None}],
            created_at=datetime(2025, 1, 1, 11, 0, 0),
            ivr_architecture=architecture,
        )

        log_step_2 = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440320"),
            execution_id=UUID("550e8400-e29b-41d4-a716-446655440313"),
            step_number=2,
            expected_text="final",
            actual_transcription="error total",
            confidence_score=12.0,
            action_taken="ASR connect error: timeout",
            created_at=datetime(2025, 1, 2, 12, 0, 2),
        )
        log_step_1 = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440321"),
            execution_id=UUID("550e8400-e29b-41d4-a716-446655440313"),
            step_number=1,
            expected_text="menu principal",
            actual_transcription="hola menu principal gracias",
            confidence_score=97.0,
            action_taken="No action (passive step)",
            created_at=datetime(2025, 1, 2, 12, 0, 1),
        )

        execution_model = SimpleNamespace(
            id=UUID("550e8400-e29b-41d4-a716-446655440313"),
            test_case_id=test_case.id,
            status="FAILED",
            duration_seconds=15,
            provider_call_sid="CA313",
            full_call_transcript="hola menu principal gracias",
            executed_at=datetime(2025, 1, 2, 12, 0, 0),
            test_case=test_case,
            logs=[log_step_2, log_step_1],
        )
        repository.get_by_id_with_details.return_value = execution_model

        response = await use_case.execute(execution_model.id)

        assert [log.step_number for log in response.logs] == [1, 2]
        assert response.logs[0].matched_excerpt == "menu principal"
        assert response.logs[1].matched_excerpt is None
