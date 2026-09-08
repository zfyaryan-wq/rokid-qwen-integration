import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from .config import Settings


def validate_enrollment_token(candidate: str, settings: Settings) -> None:
    if not settings.device_enrollment_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Device enrollment is not configured",
        )
    if not hmac.compare_digest(candidate, settings.device_enrollment_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid enrollment token",
        )


def create_device_token(device_id: str, settings: Settings) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT signing is not configured",
        )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": device_id,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=settings.device_token_ttl_seconds),
        "type": "device",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_device_token(token: str, settings: Settings) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT signing is not configured",
        )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired device token",
        ) from error
    if payload.get("type") != "device" or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device token claims",
        )
    return str(payload["sub"])


def bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return token
