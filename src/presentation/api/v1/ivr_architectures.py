from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException

from src.infrastructure.auth.dependencies import get_current_user
from src.presentation.api.v1.schemas.ivr_architecture import (
    CreateIVRArchitectureRequest,
    UpdateIVRArchitectureRequest,
)
from src.application.use_cases import (
    CreateIVRArchitectureUseCase,
    DeleteIVRArchitectureUseCase,
    ListIVRArchitecturesUseCase,
    UpdateIVRArchitectureUseCase,
)
from src.application import IVRArchitectureResponse, UpdateIVRArchitectureResponse
from src.application.exceptions import NotFoundError
from src.presentation.dependencies import (
    get_create_ivr_architecture_use_case,
    get_delete_ivr_architecture_use_case,
    get_list_ivr_architectures_use_case,
    get_update_ivr_architecture_use_case,
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


@router.put("/{architecture_id}", response_model=UpdateIVRArchitectureResponse, status_code=status.HTTP_200_OK)
async def update_ivr_architecture(
    architecture_id: UUID,
    payload: UpdateIVRArchitectureRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[UpdateIVRArchitectureUseCase, Depends(get_update_ivr_architecture_use_case)],
):
    """Actualiza una IVR Architecture existente."""
    user_id = current_user.get("id")
    
    try:
        entity = await use_case.execute(
            architecture_id=architecture_id,
            user_id=user_id,
            name=payload.name,
            phone_number=payload.phone_number,
            description=payload.description,
        )
        return UpdateIVRArchitectureResponse.model_validate(entity)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IVR Architecture not found"
        )


@router.delete("/{architecture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ivr_architecture(
    architecture_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    use_case: Annotated[
        DeleteIVRArchitectureUseCase,
        Depends(get_delete_ivr_architecture_use_case),
    ],
):
    user_id = current_user.get("id")

    try:
        await use_case.execute(architecture_id=architecture_id, user_id=user_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IVR Architecture not found",
        )
