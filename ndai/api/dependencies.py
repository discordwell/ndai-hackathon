"""Shared FastAPI dependencies."""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from ndai.config import settings

security = HTTPBearer()


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_zk_token(pubkey: str) -> str:
    """Create JWT for ZK-authenticated identity."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": pubkey, "exp": expire, "auth_type": "zk"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


async def get_zk_identity(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract and validate ZK identity from JWT. Returns hex public key."""
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[settings.algorithm]
        )
        if payload.get("auth_type") != "zk":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a ZK token")
        pubkey: str | None = payload.get("sub")
        if pubkey is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return pubkey
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract and validate the current user from JWT token.

    Rejects ZK tokens to enforce auth boundary — ZK users cannot
    access regular user endpoints.
    """
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[settings.algorithm]
        )
        if payload.get("auth_type") == "zk":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="ZK tokens not accepted"
            )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def decode_token(token: str) -> str:
    """Decode a JWT token string and return the user_id.

    Used by SSE endpoints where the token is passed as a query param
    (EventSource doesn't support Authorization headers).
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def decode_zk_token(token: str) -> str:
    """Decode a ZK JWT token string and return the pubkey.

    Used by ZK SSE endpoints. Rejects non-ZK tokens.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("auth_type") != "zk":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a ZK token"
            )
        pubkey: str | None = payload.get("sub")
        if pubkey is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return pubkey
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
