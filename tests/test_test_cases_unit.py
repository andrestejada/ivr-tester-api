"""Unit tests for Test Case schemas validation."""

import pytest
from pydantic import ValidationError

from src.presentation.api.v1.schemas.test_case import (
    FlowStep,
    CreateTestCaseRequest,
    UpdateTestCaseRequest,
)


class TestFlowStepSchema:
    """Tests para validación de FlowStep."""

    def test_valid_flow_step(self):
        step = FlowStep(step=1, listen="Bienvenido", action="send_dtmf_1")
        assert step.step == 1
        assert step.listen == "Bienvenido"
        assert step.action == "send_dtmf_1"

    def test_flow_step_action_optional(self):
        step = FlowStep(step=1, listen="Bienvenido")
        assert step.action is None

    def test_flow_step_invalid_step_zero(self):
        with pytest.raises(ValidationError):
            FlowStep(step=0, listen="Bienvenido")

    def test_flow_step_invalid_step_negative(self):
        with pytest.raises(ValidationError):
            FlowStep(step=-1, listen="Bienvenido")

    def test_flow_step_listen_empty(self):
        with pytest.raises(ValidationError):
            FlowStep(step=1, listen="")

    def test_flow_step_missing_listen(self):
        with pytest.raises(ValidationError):
            FlowStep(step=1)


class TestCreateTestCaseRequestSchema:
    """Tests para validación de CreateTestCaseRequest."""

    def test_valid_request(self):
        req = CreateTestCaseRequest(
            name="Flujo de bienvenida",
            flow_script=[
                FlowStep(step=1, listen="Bienvenido", action="send_dtmf_1"),
            ],
        )
        assert req.name == "Flujo de bienvenida"
        assert len(req.flow_script) == 1

    def test_name_empty(self):
        with pytest.raises(ValidationError):
            CreateTestCaseRequest(
                name="",
                flow_script=[FlowStep(step=1, listen="Bienvenido")],
            )

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            CreateTestCaseRequest(
                name="x" * 256,
                flow_script=[FlowStep(step=1, listen="Bienvenido")],
            )

    def test_name_max_length(self):
        req = CreateTestCaseRequest(
            name="x" * 255,
            flow_script=[FlowStep(step=1, listen="Bienvenido")],
        )
        assert len(req.name) == 255

    def test_flow_script_empty(self):
        with pytest.raises(ValidationError):
            CreateTestCaseRequest(
                name="Test",
                flow_script=[],
            )

    def test_flow_script_multiple_steps(self):
        req = CreateTestCaseRequest(
            name="Test",
            flow_script=[
                FlowStep(step=1, listen="Bienvenido", action="send_dtmf_1"),
                FlowStep(step=2, listen="Para ventas presione 2", action="send_dtmf_2"),
            ],
        )
        assert len(req.flow_script) == 2

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            CreateTestCaseRequest(
                flow_script=[FlowStep(step=1, listen="Bienvenido")],
            )

    def test_missing_flow_script(self):
        with pytest.raises(ValidationError):
            CreateTestCaseRequest(name="Test")


class TestUpdateTestCaseRequestSchema:
    """Tests para validación de UpdateTestCaseRequest."""

    def test_valid_request_name_only(self):
        req = UpdateTestCaseRequest(name="Nuevo nombre")
        assert req.name == "Nuevo nombre"
        assert req.flow_script is None

    def test_valid_request_flow_script_only(self):
        req = UpdateTestCaseRequest(
            flow_script=[FlowStep(step=1, listen="Bienvenido", action="send_dtmf_1")]
        )
        assert req.name is None
        assert len(req.flow_script) == 1

    def test_valid_request_both_fields(self):
        req = UpdateTestCaseRequest(
            name="Nuevo nombre",
            flow_script=[FlowStep(step=1, listen="Bienvenido")],
        )
        assert req.name == "Nuevo nombre"
        assert len(req.flow_script) == 1

    def test_valid_request_empty_payload(self):
        req = UpdateTestCaseRequest()
        assert req.name is None
        assert req.flow_script is None

    def test_name_empty_string(self):
        with pytest.raises(ValidationError):
            UpdateTestCaseRequest(name="")

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            UpdateTestCaseRequest(name="x" * 256)

    def test_name_max_length(self):
        req = UpdateTestCaseRequest(name="x" * 255)
        assert len(req.name) == 255

    def test_flow_script_empty_list(self):
        with pytest.raises(ValidationError):
            UpdateTestCaseRequest(flow_script=[])

    def test_flow_script_multiple_steps(self):
        req = UpdateTestCaseRequest(
            flow_script=[
                FlowStep(step=1, listen="Bienvenido", action="send_dtmf_1"),
                FlowStep(step=2, listen="Para ventas presione 2", action="send_dtmf_2"),
            ],
        )
        assert len(req.flow_script) == 2
