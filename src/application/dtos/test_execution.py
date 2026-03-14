"""DTOs for Test Execution requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExecuteTestCaseRequest(BaseModel):
    """Request DTO to execute a test case."""

    phone_number: str = Field(..., description="Phone number to call (e.g., +1234567890)")


class TestExecutionResponse(BaseModel):
    """Response DTO for a test execution."""

    id: UUID
    test_case_id: UUID
    status: str
    duration_seconds: int | None
    provider_call_sid: str | None
    executed_at: datetime

    model_config = {"from_attributes": True}
