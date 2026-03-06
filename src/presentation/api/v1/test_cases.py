"""API Router for Test Case endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.infrastructure.auth.dependencies import get_current_user
from src.presentation.api.v1.schemas.test_case import CreateTestCaseRequest
from src.application.use_cases import CreateTestCaseUseCase, ListTestCasesUseCase
from src.application.dtos import TestCaseResponse
from src.presentation.dependencies import (
    get_create_test_case_use_case,
    get_list_test_cases_use_case,
)

router = APIRouter(prefix="/ivr-architectures", tags=["test-cases"])


@router.post(
    "/{ivr_architecture_id}/test-cases",
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    ivr_architecture_id: UUID,
    payload: CreateTestCaseRequest,
    _: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[CreateTestCaseUseCase, Depends(get_create_test_case_use_case)],
):
    """Crea un nuevo Test Case para una arquitectura IVR."""
    await use_case.execute(
        ivr_architecture_id=ivr_architecture_id,
        name=payload.name,
        flow_script=[step.model_dump() for step in payload.flow_script],
    )


@router.get(
    "/{ivr_architecture_id}/test-cases",
    response_model=list[TestCaseResponse],
)
async def list_test_cases(
    ivr_architecture_id: UUID,
    _: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[ListTestCasesUseCase, Depends(get_list_test_cases_use_case)],
):
    """Lista todos los Test Cases de una arquitectura IVR."""
    return await use_case.execute(ivr_architecture_id=ivr_architecture_id)
