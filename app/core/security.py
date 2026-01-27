from functools import lru_cache
from typing import Optional

import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings


# Bearer token extractor (auto_error=False allows optional auth)
security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_jwks() -> dict:
    """Fetch Supabase JWKS for JWT verification (cached)."""
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    response = httpx.get(jwks_url, timeout=10.0)
    response.raise_for_status()
    return response.json()


def verify_jwt(token: str) -> dict:
    """Verify a Supabase JWT and return the payload."""
    try:
        # Get the algorithm from the token header
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")
        kid = unverified_header.get("kid")

        if not alg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing algorithm"
            )

        # Fetch JWKS from Supabase
        jwks = get_jwks()

        # Find the matching key by kid
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break

        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: key not found for kid={kid}"
            )

        # Decode and verify using the algorithm from the token
        # Support common algorithms: RS256, ES256, EdDSA
        allowed_algs = ["RS256", "ES256", "EdDSA", "HS256"]
        if alg not in allowed_algs:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: unsupported algorithm {alg}"
            )

        payload = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            options={"verify_aud": True}
        )

        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Get current authenticated user from JWT (optional auth)."""
    if not credentials:
        return None
    return verify_jwt(credentials.credentials)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Require authentication - raises 401 if not authenticated."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_jwt(credentials.credentials)


def verify_auth_token(authorization: str | None) -> str | None:
    """Extract auth token from Authorization header (Apple Wallet passes)."""
    if not authorization:
        return None
    if authorization.startswith("ApplePass "):
        return authorization[10:]
    return None
