"""API Router for Test Case endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException

from src.infrastructure.auth.dependencies import get_current_user
from src.presentation.api.v1.schemas.test_case import CreateTestCaseRequest, UpdateTestCaseRequest
from src.application.use_cases import (
    CreateTestCaseUseCase,
    ListTestCasesUseCase,
    UpdateTestCaseUseCase,
)
from src.application.dtos import TestCaseResponse
from src.presentation.dependencies import (
    get_create_test_case_use_case,
    get_list_test_cases_use_case,
    get_update_test_case_use_case,
)
from src.application.exceptions import NotFoundError

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


@router.put(
    "/{ivr_architecture_id}/test-cases/{test_case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_test_case(
    ivr_architecture_id: UUID,
    test_case_id: UUID,
    payload: UpdateTestCaseRequest,
    _: Annotated[dict, Depends(get_current_user)],
    list_use_case: Annotated[ListTestCasesUseCase, Depends(get_list_test_cases_use_case)],
    update_use_case: Annotated[UpdateTestCaseUseCase, Depends(get_update_test_case_use_case)],
):
    """Actualiza un Test Case existente (nombre y/o flow_script)."""
    # Verificar que el test case pertenece a la arquitectura
    try:
        test_cases = await list_use_case.execute(ivr_architecture_id=ivr_architecture_id)
        test_case_exists = any(tc.id == test_case_id for tc in test_cases)
        if not test_case_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test Case {test_case_id} not found in architecture {ivr_architecture_id}"
            )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Architecture {ivr_architecture_id} not found"
        )
    
    # Ejecutar la actualización
    try:
        await update_use_case.execute(
            test_case_id=test_case_id,
            name=payload.name,
            flow_script=[step.model_dump() for step in payload.flow_script] if payload.flow_script else None,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test Case {test_case_id} not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


