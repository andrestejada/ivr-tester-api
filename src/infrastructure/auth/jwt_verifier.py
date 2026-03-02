"""JWT token verification module for Supabase authentication."""

from typing import Any, Optional

import httpx
import jwt
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidSignatureError

from src.infrastructure.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
)
from src.infrastructure.config import settings

# Cache for JWKS
_jwks_cache: Optional[dict[str, Any]] = None


def _get_supabase_jwks() -> dict[str, Any]:
    """Fetch and cache Supabase JWKS for ES256 verification."""
    global _jwks_cache
    
    if _jwks_cache is not None:
        return _jwks_cache
    
    try:
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        response = httpx.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache
    except Exception as e:
        raise InvalidTokenError(f"Failed to fetch JWKS: {str(e)}")


def _get_key_by_kid(kid: str) -> dict[str, Any]:
    """Get JWK from JWKS by kid."""
    jwks = _get_supabase_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise InvalidTokenError(f"Key with kid '{kid}' not found")


def verify_supabase_token(token: str) -> dict[str, Any]:
    """
    Verify and decode a Supabase JWT token.

    Supports both ES256 (production tokens from Supabase) 
    and HS256 (test tokens with local secret).

    Args:
        token: JWT token string (without "Bearer " prefix)

    Returns:
        dict: Decoded token with 'id', 'email', 'user_metadata'

    Raises:
        InvalidTokenError: If token is invalid
        ExpiredTokenError: If token is expired
    """
    try:
        # Get header without verifying
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        kid = header.get("kid")
        
        # Try ES256 first (production tokens from Supabase)
        if alg == "ES256" and kid:
            try:
                from cryptography.hazmat.primitives.asymmetric import ec
                from cryptography.hazmat.backends import default_backend
                import base64
                
                key_data = _get_key_by_kid(kid)
                
                # Reconstruct EC public key from JWK
                x = int.from_bytes(base64.urlsafe_b64decode(key_data["x"] + "=="), "big")
                y = int.from_bytes(base64.urlsafe_b64decode(key_data["y"] + "=="), "big")
                curve = ec.SECP256R1()
                public_numbers = ec.EllipticCurvePublicNumbers(x, y, curve)
                public_key = public_numbers.public_key(default_backend())
                
                # Decode with the ES256 key
                decoded = jwt.decode(
                    token,
                    public_key,
                    algorithms=["ES256"],
                    audience="authenticated",
                )
                return {
                    "id": decoded.get("sub"),
                    "email": decoded.get("email"),
                    "user_metadata": decoded.get("user_metadata", {}),
                }
            except Exception:
                # If ES256 fails, continue to HS256
                pass
        
        # Fallback to HS256 (test tokens)
        decoded = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {
            "id": decoded.get("sub"),
            "email": decoded.get("email"),
            "user_metadata": decoded.get("user_metadata", {}),
        }

    except ExpiredSignatureError as e:
        raise ExpiredTokenError("Token has expired") from e

    except InvalidSignatureError as e:
        raise InvalidTokenError("Invalid token signature") from e

    except DecodeError as e:
        raise InvalidTokenError(f"Token decode error: {str(e)}") from e

    except jwt.InvalidAudienceError as e:
        raise InvalidTokenError("Invalid token audience") from e

    except Exception as e:
        raise InvalidTokenError(f"Token verification failed: {str(e)}") from e
