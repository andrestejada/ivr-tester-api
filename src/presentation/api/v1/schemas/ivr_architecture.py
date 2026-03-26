from pydantic import BaseModel, Field, field_validator
import re


class CreateIVRArchitectureRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=250)
    phone_number: str = Field(..., min_length=1)
    description: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v) > 250:
            raise ValueError("El nombre debe tener entre 1 y 250 caracteres")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        # Permitir formato internacional: +[dígitos], con espacios y guiones opcionales
        if not re.match(r"^\+?[\d\s-]+$", v):
            raise ValueError("El teléfono debe contener solo números, +, espacios o guiones")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v and len(v) > 500:
            raise ValueError("La descripción no debe exceder 500 caracteres")
        return v