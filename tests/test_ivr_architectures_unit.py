import pytest
from src.presentation.api.v1.schemas.ivr_architecture import (
    CreateIVRArchitectureRequest,
)
from pydantic import ValidationError


class TestCreateIVRArchitectureRequestSchema:
    def test_valid_payload(self):
        req = CreateIVRArchitectureRequest(name="Sales IVR", phone_number="5551234567")
        assert req.name == "Sales IVR"
        assert req.phone_number == "5551234567"
        assert req.description is None

    def test_name_empty(self):
        with pytest.raises(ValidationError):
            CreateIVRArchitectureRequest(name="", phone_number="5551234567")

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            CreateIVRArchitectureRequest(name="x" * 251, phone_number="5551234567")

    def test_name_max_length(self):
        req = CreateIVRArchitectureRequest(name="x" * 250, phone_number="5551234567")
        assert len(req.name) == 250

    def test_phone_number_valid(self):
        req = CreateIVRArchitectureRequest(name="Sales IVR", phone_number="5551234567")
        assert req.phone_number == "5551234567"

    def test_phone_number_with_letters(self):
        with pytest.raises(ValidationError):
            CreateIVRArchitectureRequest(name="Sales IVR", phone_number="555-ABC-1234")

    def test_phone_number_with_special_chars(self):
        with pytest.raises(ValidationError):
            CreateIVRArchitectureRequest(name="Sales IVR", phone_number="555-123-4567")

    def test_phone_number_empty(self):
        with pytest.raises(ValidationError):
            CreateIVRArchitectureRequest(name="Sales IVR", phone_number="")

    def test_description_optional(self):
        req = CreateIVRArchitectureRequest(name="Sales IVR", phone_number="5551234567")
        assert req.description is None

    def test_description_too_long(self):
        with pytest.raises(ValidationError):
            CreateIVRArchitectureRequest(
                name="Sales IVR",
                phone_number="5551234567",
                description="x" * 501,
            )
