"""FastAPI dependency injection for JWT authentication."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    MissingTokenError,
)
from src.infrastructure.auth.jwt_verifier import verify_supabase_token

# Security scheme for OpenAPI documentation
oauth2_scheme = HTTPBearer(
    description="JWT token from Supabase Authentication",
    auto_error=False,  # Handle missing token manually for better error messages
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(oauth2_scheme)]
) -> dict:
    """
    Dependency to extract and validate JWT token from request header.

    Validates token signature, expiration, and audience claim.
    Returns user info extracted from token.

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        dict: User info with keys: 'id', 'email', 'user_metadata'

    Raises:
        HTTPException 401: If token is missing, invalid, or expired
    """
    # Check if credentials are provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        user = verify_supabase_token(token)
        
        try:
            user["id"] = UUID(user.get("id"))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user

    except ExpiredTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except MissingTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
