"""API Router for Test Execution endpoints (listing only)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.infrastructure.auth.dependencies import get_current_user
from src.application.use_cases import ListTestExecutionsUseCase
from src.application.dtos import TestExecutionResponse
from src.presentation.dependencies import get_list_test_executions_use_case

router = APIRouter(prefix="/ivr-architectures", tags=["test-executions"])


@router.get(
    "/{ivr_architecture_id}/test-cases/{test_case_id}/executions",
    response_model=list[TestExecutionResponse],
)
async def list_test_executions(
    ivr_architecture_id: UUID,
    test_case_id: UUID,
    _: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[ListTestExecutionsUseCase, Depends(get_list_test_executions_use_case)],
):
    """Lista las ejecuciones de un Test Case específico."""
    # ivr_architecture_id se recibe para mantener la jerarquía de ruta,
    # aunque actualmente no se utiliza en la lógica.
    return await use_case.execute(test_case_id=test_case_id)
