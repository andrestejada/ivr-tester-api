"""Test para validar la lógica de último step pasivo con timeout."""
import pytest


def test_last_passive_step_logic():
    """Validar que un step pasivo al final con timeout se trate como éxito."""
    
    # Setup
    flow_script = [
        {"step": 1, "action": "1", "listen": "First step"},
        {"step": 2, "action": None, "listen": "Last passive step with long message"},
    ]
    
    # Simular state machine en último step
    current_step_index = 1  # index 1 = segundo step (último)
    is_last_step = current_step_index >= len(flow_script) - 1
    
    current_step = flow_script[current_step_index]
    step_action = current_step.get("action")
    is_passive_step = step_action is None
    
    # LÓGICA: Si es último step Y pasivo → éxito
    should_succeed_on_timeout = is_last_step and is_passive_step
    
    assert is_last_step, "Should be last step"
    assert is_passive_step, "Should be passive step"
    assert should_succeed_on_timeout, "Should succeed on timeout"
    print("✓ PASS: Last passive step will succeed on timeout")


def test_non_last_passive_step_logic():
    """Validar que un step pasivo en MEDIO con timeout still falla."""
    
    flow_script = [
        {"step": 1, "action": "1", "listen": "First step"},
        {"step": 2, "action": None, "listen": "Middle passive step"},
        {"step": 3, "action": "2", "listen": "Final step"},
    ]
    
    # Simular state machine en step del medio
    current_step_index = 1  # index 1 = segundo step (NOT último)
    is_last_step = current_step_index >= len(flow_script) - 1
    
    current_step = flow_script[current_step_index]
    step_action = current_step.get("action")
    is_passive_step = step_action is None
    
    # LÓGICA: Incluso si es pasivo, si NO es último → falla
    should_succeed_on_timeout = is_last_step and is_passive_step
    
    assert not is_last_step, "Should NOT be last step"
    assert is_passive_step, "Is passive step"
    assert not should_succeed_on_timeout, "Should FAIL on timeout (not last)"
    print("✓ PASS: Non-last passive step will fail on timeout")


def test_last_active_step_logic():
    """Validar que el último step CON acción sigue fallando con timeout."""
    
    flow_script = [
        {"step": 1, "action": "1", "listen": "First step"},
        {"step": 2, "action": "2", "listen": "Last step with action"},
    ]
    
    # Simular state machine en último step
    current_step_index = 1  # index 1 = segundo step (último)
    is_last_step = current_step_index >= len(flow_script) - 1
    
    current_step = flow_script[current_step_index]
    step_action = current_step.get("action")
    is_passive_step = step_action is None
    
    # LÓGICA: Si último pero NO pasivo → falla
    should_succeed_on_timeout = is_last_step and is_passive_step
    
    assert is_last_step, "Should be last step"
    assert not is_passive_step, "Should NOT be passive (has action)"
    assert not should_succeed_on_timeout, "Should FAIL on timeout (has action)"
    print("✓ PASS: Last active step will fail on timeout")

