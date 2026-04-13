"""DTOs for Test Execution Details — complete forensic view with nested relations."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ExecutionLogResponse(BaseModel):
    """Response DTO for an execution step log."""

    id: UUID
    execution_id: UUID
    step_number: int
    expected_text: str | None
    actual_transcription: str | None
    confidence_score: Decimal | None
    action_taken: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IVRArchitectureDetailResponse(BaseModel):
    """Response DTO for IVR Architecture (nested in execution details)."""

    id: UUID
    user_id: UUID
    name: str
    phone_number: str
    provider: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TestCaseDetailResponse(BaseModel):
    """Response DTO for Test Case (nested in execution details)."""

    id: UUID
    ivr_architecture_id: UUID
    name: str
    flow_script: list[dict]
    created_at: datetime
    # Nested architecture
    ivr_architecture: IVRArchitectureDetailResponse

    model_config = {"from_attributes": True}


class TestExecutionDetailsResponse(BaseModel):
    """Complete forensic response for a test execution with all related data.
    
    Includes:
    - Execution metadata (id, status, duration, provider_call_sid, executed_at)
    - Associated Test Case with its IVR Architecture
    - Ordered list of execution step logs for analysis
    - Full call transcript for debugging and audit purposes
    """

    id: UUID
    test_case_id: UUID
    status: str
    duration_seconds: int | None
    provider_call_sid: str | None
    full_call_transcript: str | None = None
    executed_at: datetime
    # Nested relations
    test_case: TestCaseDetailResponse
    logs: list[ExecutionLogResponse]

    model_config = {"from_attributes": True}
