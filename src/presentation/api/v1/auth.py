"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.infrastructure.auth.dependencies import get_current_user

router = APIRouter(tags=["auth"])


@router.get("/me")
async def get_current_user_info(
    current_user: Annotated[dict, Depends(get_current_user)]
) -> dict:
    """
    Retrieve current authenticated user information.

    Requires valid JWT token in Authorization header.

    Returns:
        dict: User information containing 'id', 'email', and 'user_metadata'

    Raises:
        401 Unauthorized: If token is missing, invalid, or expired
    """
    return {
        "id": current_user.get("id"),
        "email": current_user.get("email"),
        "user_metadata": current_user.get("user_metadata", {}),
    }
