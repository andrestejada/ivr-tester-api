"""DTOs for Test Execution responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TestExecutionResponse(BaseModel):
    """Response DTO for a test execution."""

    id: UUID
    test_case_id: UUID
    status: str
    duration_seconds: int | None
    provider_call_sid: str | None
    executed_at: datetime

    model_config = {"from_attributes": True}
