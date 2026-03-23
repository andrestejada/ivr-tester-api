"""API Router for Test Execution endpoints."""

import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.infrastructure.auth.dependencies import get_current_user
from src.infrastructure.config import settings
from src.application.use_cases import ListTestExecutionsUseCase
from src.application.use_cases.execute_test_case_use_case import ExecuteTestCaseUseCase
from src.application.dtos import TestExecutionResponse
from src.application.dtos.test_execution import ExecuteTestCaseRequest
from src.domain.repositories.ivr_architecture_repository import IIVRArchitectureRepository
from src.presentation.dependencies import get_list_test_executions_use_case
from src.presentation.dependencies.execution_dependencies import (
    get_execute_test_case_use_case,
)
from src.presentation.dependencies.ivr_architecture_dependencies import (
    get_ivr_architecture_repo,
)

router = APIRouter(prefix="/ivr-architectures", tags=["test-executions"])
logger = logging.getLogger(__name__)


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


@router.post(
    "/{ivr_architecture_id}/test-cases/{test_case_id}/executions",
    response_model=TestExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_test_case(
    ivr_architecture_id: UUID,
    test_case_id: UUID,
    request: ExecuteTestCaseRequest,
    _: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[ExecuteTestCaseUseCase, Depends(get_execute_test_case_use_case)],
    ivr_repo: Annotated[IIVRArchitectureRepository, Depends(get_ivr_architecture_repo)],
):
    """Inicia la ejecución de un Test Case contra IVR.
    
    Retorna 202 Accepted con la ejecución en estado RUNNING.
    La ejecución de la llamada se procesa en background dentro del Use Case.
    """
    # Obtener arquitectura para extraer el provider
    architecture = await ivr_repo.get_by_id(ivr_architecture_id)
    
    # Construir webhook_url dinámicamente basada en el provider
    webhook_url = f"{settings.base_url}/webhooks/{architecture.provider}/voice"
    
    logger.info(
        "Executing test case with provider=%s webhook_url=%s",
        architecture.provider,
        webhook_url,
    )

    # Ejecutar use case. Éste ya se encarga de crear el registro RUNNING 
    # y lanzar la tarea pesada en background (asyncio.create_task).
    execution = await use_case.execute(
        test_case_id=test_case_id,
        phone_number=request.phone_number,
        webhook_url=webhook_url,
    )
    
    return TestExecutionResponse(
        id=execution.id,
        test_case_id=execution.test_case_id,
        status=execution.status,
        duration_seconds=execution.duration_seconds,
        provider_call_sid=execution.provider_call_sid,
        executed_at=execution.executed_at,
    )
