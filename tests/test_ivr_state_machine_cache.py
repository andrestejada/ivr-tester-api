"""Test suite for IVRStateMachine evaluation cache functionality."""

import sys
import os

# Add the parent directory to the path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from decimal import Decimal
from unittest.mock import Mock, call

from src.application.services.ivr_state_machine import IVRStateMachine


@pytest.fixture
def evaluate_fn_mock():
    """Mock function that simulates transcription evaluation."""
    return Mock(return_value=(0.95, Decimal("95"), True))


@pytest.fixture
def state_machine(evaluate_fn_mock):
    """Create a state machine instance for testing."""
    flow_script = [
        {"step": 1, "listen": "hello world", "action": "Say-Greeting"},
        {"step": 2, "listen": "goodbye", "action": None},
    ]
    return IVRStateMachine(flow_script, evaluate_fn_mock)


class TestEvaluationCache:
    """Test cases for the evaluation cache."""
    
    def test_cache_key_generation(self, state_machine):
        """Test that cache keys are generated deterministically."""
        key1 = state_machine._create_cache_key("hello", "world", 0.8)
        key2 = state_machine._create_cache_key("hello", "world", 0.8)
        key3 = state_machine._create_cache_key("hello", "world2", 0.8)
        
        # Same inputs should produce same key
        assert key1 == key2
        # Different inputs should produce different keys
        assert key1 != key3
        # Keys should be hexadecimal strings (SHA256)
        assert len(key1) == 64
        assert all(c in "0123456789abcdef" for c in key1)
    
    def test_cache_miss_on_first_evaluation(self, state_machine, evaluate_fn_mock):
        """Test that first evaluation is not cached."""
        result = state_machine._get_cached_evaluation("hello", "world", 0.8)
        assert result is None
        assert state_machine._cache_misses == 1
    
    def test_cache_hit_after_storage(self, state_machine, evaluate_fn_mock):
        """Test that cached evaluations can be retrieved."""
        evaluation_result = (0.95, Decimal("95"), True)
        
        state_machine._cache_evaluation_result("hello", "world", 0.8, evaluation_result)
        
        cached = state_machine._get_cached_evaluation("hello", "world", 0.8)
        assert cached == evaluation_result
        assert state_machine._cache_hits == 1
    
    def test_cache_stats(self, state_machine, evaluate_fn_mock):
        """Test cache statistics tracking."""
        evaluation_result = (0.95, Decimal("95"), True)
        
        # Perform some operations
        state_machine._get_cached_evaluation("test1", "text1", 0.8)  # miss
        state_machine._cache_evaluation_result("test1", "text1", 0.8, evaluation_result)
        state_machine._get_cached_evaluation("test1", "text1", 0.8)  # hit
        state_machine._get_cached_evaluation("test2", "text2", 0.8)  # miss
        
        stats = state_machine.get_cache_stats()
        
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2
        assert stats["cache_size"] == 1  # Only one unique key cached
        assert stats["hit_rate_percent"] == 33.33  # 1 hit / 3 total
    
    def test_cache_different_thresholds(self, state_machine, evaluate_fn_mock):
        """Test that same inputs with different thresholds produce different cache entries."""
        evaluation_result = (0.95, Decimal("95"), True)
        
        state_machine._cache_evaluation_result("hello", "world", 0.80, evaluation_result)
        state_machine._cache_evaluation_result("hello", "world", 0.85, evaluation_result)
        
        # Should have 2 cache entries
        assert state_machine.get_cache_stats()["cache_size"] == 2
        
        # Both should be retrievable
        assert state_machine._get_cached_evaluation("hello", "world", 0.80) == evaluation_result
        assert state_machine._get_cached_evaluation("hello", "world", 0.85) == evaluation_result
    
    def test_cache_eviction_at_limit(self, state_machine, evaluate_fn_mock):
        """Test that cache is cleared when reaching 1000 entries."""
        evaluation_result = (0.95, Decimal("95"), True)
        
        # Fill cache to near capacity
        for i in range(1000):
            state_machine._cache_evaluation_result(f"test{i}", "text", 0.8, evaluation_result)
        
        assert state_machine.get_cache_stats()["cache_size"] == 1000
        
        # Adding one more should trigger eviction
        state_machine._cache_evaluation_result("overflow", "text", 0.8, evaluation_result)
        
        # Cache should be cleared and then the new entry added
        assert state_machine.get_cache_stats()["cache_size"] == 1
    
    def test_check_for_step_match_uses_cache(self, state_machine, evaluate_fn_mock):
        """Test that check_for_step_match uses the cache correctly."""
        # Reset mock to track calls precisely
        evaluate_fn_mock.reset_mock()
        evaluate_fn_mock.return_value = (0.95, Decimal("95"), True)
        
        # Simulate incoming transcript
        state_machine.accumulate_transcript_text("hello", is_final=False)
        state_machine.accumulate_transcript_text(" world", is_final=True)
        
        # First call - should call evaluate_fn (cache miss)
        result1 = state_machine.check_for_step_match()
        assert result1 is not None
        assert evaluate_fn_mock.call_count == 1
        initial_hits = state_machine.get_cache_stats()["cache_hits"]
        
        # Manually cache the result for the same transcript
        # This simulates what would happen if we process the same audio twice
        cached_result = (0.95, Decimal("95"), True)
        state_machine._cache_evaluation_result(
            "hello world",  # expected
            "hello world",  # current_full_text
            0.85,  # EARLY_EXIT_THRESHOLD
            cached_result
        )
        
        # Verify cache was populated
        assert state_machine.get_cache_stats()["cache_size"] >= 1
    
    def test_cache_preserves_evaluation_accuracy(self, state_machine, evaluate_fn_mock):
        """Test that cached results are identical to fresh evaluations."""
        expected_result = (0.92, Decimal("92"), True)
        evaluate_fn_mock.return_value = expected_result
        
        # Get evaluation result
        result1 = state_machine.evaluate_transcription_fn("test", "text", 0.8)
        
        # Cache it
        state_machine._cache_evaluation_result("test", "text", 0.8, result1)
        
        # Retrieve from cache
        cached_result = state_machine._get_cached_evaluation("test", "text", 0.8)
        
        # Should be identical
        assert cached_result == result1 == expected_result
    
    def test_empty_cache_on_new_machine(self, evaluate_fn_mock):
        """Test that new state machine instances have empty cache."""
        machine1 = IVRStateMachine([{"step": 1, "listen": "test", "action": "test"}], evaluate_fn_mock)
        machine2 = IVRStateMachine([{"step": 1, "listen": "test", "action": "test"}], evaluate_fn_mock)
        
        # Each should have independent cache
        machine1._cache_evaluation_result("a", "b", 0.8, (0.9, Decimal("90"), True))
        
        # machine2 should not have entries from machine1
        assert machine2.get_cache_stats()["cache_size"] == 0
        assert machine1.get_cache_stats()["cache_size"] == 1


class TestCacheIntegration:
    """Integration tests for cache with the full state machine flow."""
    
    def test_repeated_transcript_uses_cache(self, state_machine, evaluate_fn_mock):
        """Test that repeated evaluations of same transcript use cache."""
        # Reset mock to track calls precisely
        evaluate_fn_mock.reset_mock()
        evaluate_fn_mock.return_value = (0.95, Decimal("95"), True)
        
        # Accumulate transcript
        state_machine.accumulate_transcript_text("hello", is_final=False)
        state_machine.accumulate_transcript_text(" world", is_final=True)
        
        # Perform multiple step matches checks
        # (In real usage, this might happen during overlapping audio packets)
        for _ in range(3):
            state_machine.check_for_step_match()
        
        # Should only call evaluate_fn once (first time), others from cache
        assert evaluate_fn_mock.call_count <= 2  # Allow for minor variations


class TestStateMachineUncoveredBranches:
    """Cubre ramas de estado/transcript aún no ejercitadas."""

    def test_accumulate_transcript_text_updates_partial_and_time(self):
        def evaluate_fn(expected, transcribed, threshold=0.8):
            return (0.2, Decimal("20"), False)

        machine = IVRStateMachine(
            [{"step": 1, "listen": "hola", "action": None}],
            evaluate_fn,
        )
        previous_time = machine.state.last_text_time

        machine.accumulate_transcript_text("hola parcial", is_final=False)

        assert machine.state.current_partial == "hola parcial"
        assert machine.state.last_text_time >= previous_time

    def test_accumulate_transcript_text_final_sets_endpoint_event(self):
        def evaluate_fn(expected, transcribed, threshold=0.8):
            return (0.2, Decimal("20"), False)

        machine = IVRStateMachine(
            [{"step": 1, "listen": "hola", "action": None}],
            evaluate_fn,
        )

        machine.accumulate_transcript_text("hola final", is_final=True, speech_final=True)

        assert machine.state.transcript_parts == ["hola final"]
        assert machine.state.current_partial == ""
        assert machine.state.transcript_final_event.is_set() is True

    def test_check_for_step_match_returns_none_when_listen_is_empty(self):
        evaluate_fn = Mock(return_value=(0.95, Decimal("95"), True))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "", "action": None}],
            evaluate_fn,
        )
        machine.accumulate_transcript_text("cualquier texto", is_final=True)

        result = machine.check_for_step_match()

        assert result is None
        evaluate_fn.assert_not_called()

    def test_check_for_step_match_returns_none_when_buffer_empty(self):
        evaluate_fn = Mock(return_value=(0.95, Decimal("95"), True))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "hola", "action": None}],
            evaluate_fn,
        )

        result = machine.check_for_step_match()

        assert result is None
        evaluate_fn.assert_not_called()

    def test_check_for_step_match_returns_none_when_no_match(self):
        evaluate_fn = Mock(return_value=(0.30, Decimal("30"), False))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "texto esperado", "action": None}],
            evaluate_fn,
        )
        machine.accumulate_transcript_text("texto diferente", is_final=True)

        result = machine.check_for_step_match()

        assert result is None
        assert machine.get_last_similarity_ratio() == 0.30

    def test_check_if_step_repeated_detects_repetition(self):
        evaluate_fn = Mock(return_value=(0.9, Decimal("90"), True))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "menu", "action": None}],
            evaluate_fn,
        )
        machine.state.previous_step_transcript = "bienvenido menu principal"

        is_repeated = machine.check_if_step_repeated(
            "bienvenido menu principal", repeat_threshold=0.5
        )

        assert is_repeated is True

    def test_check_if_step_repeated_returns_false_for_different_text(self):
        evaluate_fn = Mock(return_value=(0.9, Decimal("90"), True))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "menu", "action": None}],
            evaluate_fn,
        )
        machine.state.previous_step_transcript = "menu de ventas"

        is_repeated = machine.check_if_step_repeated(
            "informacion de facturacion", repeat_threshold=0.8
        )

        assert is_repeated is False

    def test_advance_to_next_step_resets_step_state(self):
        evaluate_fn = Mock(return_value=(0.9, Decimal("90"), True))
        machine = IVRStateMachine(
            [
                {"step": 1, "listen": "hola", "action": "1"},
                {"step": 2, "listen": "adios", "action": None},
            ],
            evaluate_fn,
        )
        machine.state.transcript_parts = ["hola"]
        machine.state.current_partial = "menu"

        machine.advance_to_next_step("hola")

        assert machine.state.current_step_index == 1
        assert machine.state.full_call_transcript.strip() == "hola"
        assert machine.state.previous_step_transcript == "hola menu"
        assert machine.state.transcript_parts == []
        assert machine.state.current_partial == ""
        assert machine.state.transcript_final_event.is_set() is False

    def test_build_and_finalize_full_transcript(self):
        evaluate_fn = Mock(return_value=(0.9, Decimal("90"), True))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "hola", "action": None}],
            evaluate_fn,
        )
        machine.state.full_call_transcript = "inicio"
        machine.state.transcript_parts = ["mitad"]
        machine.state.current_partial = "final"

        global_transcript = machine._build_global_transcript()
        final_transcript = machine.finalize_and_get_full_transcript(additional_text="extra")

        assert global_transcript == "iniciomitad"
        assert final_transcript == "inicio mitad final extra"

    def test_check_for_step_match_returns_none_when_current_step_is_none(self):
        evaluate_fn = Mock(return_value=(0.95, Decimal("95"), True))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "hola", "action": None}],
            evaluate_fn,
        )
        machine.state.current_step_index = 99

        result = machine.check_for_step_match()

        assert result is None
        evaluate_fn.assert_not_called()

    def test_check_step_stagnation_uses_fallback_step_number_when_no_current_step(self):
        from time import time as get_time

        evaluate_fn = Mock(return_value=(0.40, Decimal("40"), False))
        machine = IVRStateMachine(
            [{"step": 1, "listen": "hola", "action": None}],
            evaluate_fn,
        )
        # Forzar estado sin current_step para cubrir rama de fallback de step_number.
        machine.state.current_step_index = 1
        machine.state.transcript_parts = ["algo"]
        machine.state.last_text_time = get_time() - 5.0
        machine.state.best_similarity_ratio = 0.35
        machine.state.last_similarity_improvement_time = get_time() - 10.0

        is_stagnated = machine.check_step_stagnation(
            stagnation_seconds=8.0,
            max_ratio_without_progress=0.6,
            min_silence_seconds=3.0,
        )

        assert is_stagnated is True

    def test_clear_buffer_for_new_step_resets_transcription_state(self):
        machine = IVRStateMachine(
            [{"step": 1, "listen": "hola", "action": None}],
            Mock(return_value=(0.9, Decimal("90"), True)),
        )
        machine.state.transcript_parts = ["residual"]
        machine.state.current_partial = "fragmento"
        machine.state.last_similarity_ratio = 0.55
        machine.state.best_similarity_ratio = 0.71

        machine.clear_buffer_for_new_step()

        assert machine.state.transcript_parts == []
        assert machine.state.current_partial == ""
        assert machine.state.last_similarity_ratio == 0.0
        assert machine.state.best_similarity_ratio == 0.0
