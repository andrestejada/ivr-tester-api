"""DTO for Test Case responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TestCaseResponse(BaseModel):
    """Response DTO for Test Case."""

    id: UUID
    ivr_architecture_id: UUID
    name: str
    flow_script: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}
