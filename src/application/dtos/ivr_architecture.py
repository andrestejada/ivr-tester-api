from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IVRArchitectureResponse(BaseModel):
    id: UUID
    name: str
    phone_number: str
    provider: str
    description: str | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UpdateIVRArchitectureResponse(BaseModel):
    id: UUID
    name: str
    phone_number: str
    provider: str
    description: str | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
