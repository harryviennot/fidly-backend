import logging
from functools import lru_cache
from typing import Optional

import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

logger = logging.getLogger(__name__)

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
            logger.warning("JWT missing algorithm in header")
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
            # JWKS might be stale — clear cache and retry once
            logger.warning(f"JWT kid={kid} not found in cached JWKS, refreshing...")
            get_jwks.cache_clear()
            jwks = get_jwks()
            for k in jwks.get("keys", []):
                if k.get("kid") == kid:
                    key = k
                    break

        if not key:
            logger.error(f"JWT kid={kid} not found even after JWKS refresh. Available kids: {[k.get('kid') for k in jwks.get('keys', [])]}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: key not found for kid={kid}"
            )

        # Decode and verify using the algorithm from the token
        # Support common algorithms: RS256, ES256, EdDSA
        allowed_algs = ["RS256", "ES256", "EdDSA", "HS256"]
        if alg not in allowed_algs:
            logger.warning(f"JWT unsupported algorithm: {alg}")
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
        logger.warning(f"JWT verification failed: {e}")
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
        logger.warning("Auth required but no Bearer token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_jwt(credentials.credentials)


def require_superadmin(auth_payload: dict = Depends(require_auth)) -> dict:
    """Require superadmin access - raises 403 if not a superadmin."""
    app_metadata = auth_payload.get("app_metadata", {})
    if not app_metadata.get("is_superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return auth_payload


def verify_auth_token(authorization: str | None) -> str | None:
    """Extract auth token from Authorization header (Apple Wallet passes)."""
    if not authorization:
        return None
    if authorization.startswith("ApplePass "):
        return authorization[10:]
    return None
