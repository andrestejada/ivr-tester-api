from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.infrastructure.auth.dependencies import get_current_user
from src.presentation.api.v1.schemas.ivr_architecture import CreateIVRArchitectureRequest
from src.application.use_cases import CreateIVRArchitectureUseCase, ListIVRArchitecturesUseCase
from src.application import IVRArchitectureResponse
from src.presentation.dependencies import (
    get_create_ivr_architecture_use_case,
    get_list_ivr_architectures_use_case,
)

router = APIRouter(prefix="/ivr-architectures", tags=["ivr-architectures"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ivr_architecture(
    payload: CreateIVRArchitectureRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[CreateIVRArchitectureUseCase, Depends(get_create_ivr_architecture_use_case)],
):
    user_id = current_user.get("id")

    await use_case.execute(
        name=payload.name,
        phone_number=payload.phone_number,
        user_id=user_id,
        description=payload.description,
    )


@router.get("", response_model=list[IVRArchitectureResponse])
async def list_ivr_architectures(
    current_user: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[ListIVRArchitecturesUseCase, Depends(get_list_ivr_architectures_use_case)],
):
    user_id = current_user.get("id")
    return await use_case.execute(user_id=user_id)
