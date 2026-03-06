"""Presentation schemas for Test Case endpoints."""

from pydantic import BaseModel, Field


class FlowStep(BaseModel):
    """Schema para un paso del flujo de prueba."""

    step: int = Field(..., ge=1, description="Número secuencial del paso")
    listen: str = Field(..., min_length=1, description="Texto esperado del IVR")
    action: str | None = Field(None, description="Acción a ejecutar (ej: send_dtmf_1)")


class CreateTestCaseRequest(BaseModel):
    """Schema para crear un nuevo Test Case."""

    name: str = Field(..., min_length=1, max_length=255, description="Nombre del caso de prueba")
    flow_script: list[FlowStep] = Field(..., min_length=1, description="Lista de pasos del flujo")
