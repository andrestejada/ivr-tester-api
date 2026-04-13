import pytest
from src.presentation.api.v1.schemas.ivr_architecture import (
    CreateIVRArchitectureRequest,
    UpdateIVRArchitectureRequest,
)
from pydantic import ValidationError
from datetime import datetime
from uuid import UUID


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

    def test_phone_number_with_plus(self):
        req = CreateIVRArchitectureRequest(name="Sales IVR", phone_number="+5551234567")
        assert req.phone_number == "+5551234567"

    def test_phone_number_with_spaces_and_dashes(self):
        req = CreateIVRArchitectureRequest(name="Sales IVR", phone_number="+555 123-4567")
        assert req.phone_number == "+555 123-4567"

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


class TestUpdateIVRArchitectureRequestSchema:
    def test_valid_payload(self):
        req = UpdateIVRArchitectureRequest(name="Updated IVR", phone_number="+12025551234")
        assert req.name == "Updated IVR"
        assert req.phone_number == "+12025551234"
        assert req.description is None

    def test_name_empty(self):
        with pytest.raises(ValidationError):
            UpdateIVRArchitectureRequest(name="", phone_number="5551234567")

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            UpdateIVRArchitectureRequest(name="x" * 251, phone_number="5551234567")

    def test_name_max_length(self):
        req = UpdateIVRArchitectureRequest(name="x" * 250, phone_number="5551234567")
        assert len(req.name) == 250

    def test_phone_number_valid(self):
        req = UpdateIVRArchitectureRequest(name="Sales IVR", phone_number="5551234567")
        assert req.phone_number == "5551234567"

    def test_phone_number_with_letters(self):
        with pytest.raises(ValidationError):
            UpdateIVRArchitectureRequest(name="Sales IVR", phone_number="555-ABC-1234")

    def test_phone_number_with_plus(self):
        req = UpdateIVRArchitectureRequest(name="Sales IVR", phone_number="+5551234567")
        assert req.phone_number == "+5551234567"

    def test_phone_number_with_spaces_and_dashes(self):
        req = UpdateIVRArchitectureRequest(name="Sales IVR", phone_number="+555 123-4567")
        assert req.phone_number == "+555 123-4567"

    def test_phone_number_empty(self):
        with pytest.raises(ValidationError):
            UpdateIVRArchitectureRequest(name="Sales IVR", phone_number="")

    def test_description_optional(self):
        req = UpdateIVRArchitectureRequest(name="Sales IVR", phone_number="5551234567")
        assert req.description is None

    def test_description_too_long(self):
        with pytest.raises(ValidationError):
            UpdateIVRArchitectureRequest(
                name="Sales IVR",
                phone_number="5551234567",
                description="x" * 501,
            )

    def test_description_max_length(self):
        req = UpdateIVRArchitectureRequest(
            name="Sales IVR",
            phone_number="5551234567",
            description="x" * 500,
        )
        assert len(req.description) == 500


class TestListIVRArchitecturesUseCase:
    """Tests para el caso de uso de listar arquitecturas IVR por usuario."""

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list_when_no_architectures(self):
        """Verifica que retorna lista vacía cuando no hay arquitecturas."""
        from src.application.use_cases.list_ivr_architectures_use_case import (
            ListIVRArchitecturesUseCase,
        )

        class FakeRepo:
            async def list_by_user(self, user_id):
                return []

        use_case = ListIVRArchitecturesUseCase(FakeRepo())

        result = await use_case.execute(UUID("550e8400-e29b-41d4-a716-446655440000"))

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_execute_maps_entities_to_dtos(self):
        """Verifica que mapea entidades a DTOs correctamente."""
        from src.application.use_cases.list_ivr_architectures_use_case import (
            ListIVRArchitecturesUseCase,
        )
        from src.domain.entities.ivr_architecture import IVRArchitectureEntity

        user_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        arch_id = UUID("550e8400-e29b-41d4-a716-446655440001")

        class FakeRepo:
            async def list_by_user(self, uid):
                return [
                    IVRArchitectureEntity(
                        id=arch_id,
                        name="Sales IVR",
                        phone_number="5551234567",
                        description="Main sales flow",
                        provider="twilio",
                        user_id=uid,
                        created_at=datetime(2025, 1, 1, 10, 0, 0),
                    )
                ]

        use_case = ListIVRArchitecturesUseCase(FakeRepo())

        result = await use_case.execute(user_id)

        assert len(result) == 1
        assert result[0].id == arch_id
        assert result[0].name == "Sales IVR"
        assert result[0].phone_number == "5551234567"
        assert result[0].description == "Main sales flow"
        assert result[0].provider == "twilio"
        assert result[0].created_at == datetime(2025, 1, 1, 10, 0, 0)

    @pytest.mark.asyncio
    async def test_execute_maps_multiple_architectures(self):
        """Verifica que mapea múltiples entidades correctamente."""
        from src.application.use_cases.list_ivr_architectures_use_case import (
            ListIVRArchitecturesUseCase,
        )
        from src.domain.entities.ivr_architecture import IVRArchitectureEntity

        user_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        arch_id_1 = UUID("550e8400-e29b-41d4-a716-446655440001")
        arch_id_2 = UUID("550e8400-e29b-41d4-a716-446655440002")

        class FakeRepo:
            async def list_by_user(self, uid):
                return [
                    IVRArchitectureEntity(
                        id=arch_id_1,
                        name="Sales IVR",
                        phone_number="5551234567",
                        description="Sales flow",
                        provider="twilio",
                        user_id=uid,
                        created_at=datetime(2025, 1, 1, 10, 0, 0),
                    ),
                    IVRArchitectureEntity(
                        id=arch_id_2,
                        name="Support IVR",
                        phone_number="5559876543",
                        description="Support flow",
                        provider="deepgram",
                        user_id=uid,
                        created_at=datetime(2025, 1, 2, 11, 0, 0),
                    ),
                ]

        use_case = ListIVRArchitecturesUseCase(FakeRepo())

        result = await use_case.execute(user_id)

        assert len(result) == 2
        assert result[0].id == arch_id_1
        assert result[0].name == "Sales IVR"
        assert result[1].id == arch_id_2
        assert result[1].name == "Support IVR"
