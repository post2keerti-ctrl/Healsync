"""FastAPI authentication dependency for Firebase ID tokens."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import ENABLE_DEV_AUTH, ENVIRONMENT
from .firebase import verify_id_token

bearer = HTTPBearer(auto_error=True)


def _dev_jwt_secret() -> str:
    secret = os.getenv("DEV_JWT_SECRET")
    if secret:
        return secret
    if ENVIRONMENT == "development":
        return "dev-only-secret-change-me"
    raise RuntimeError("DEV_JWT_SECRET must be configured when demo authentication is enabled")


def issue_dev_token(uid: str, email: str) -> str:
    payload = {
        "uid": uid,
        "email": email,
        "name": email.split("@")[0],
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, _dev_jwt_secret(), algorithm="HS256")


def verify_dev_token(token: str) -> dict:
    payload = jwt.decode(token, _dev_jwt_secret(), algorithms=["HS256"])
    return {
        "uid": payload["uid"],
        "email": payload.get("email", ""),
        "name": payload.get("name") or payload.get("email", "").split("@")[0],
    }


def current_claims(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    token = credentials.credentials
    try:
        return verify_id_token(token)
    except Exception:
        if ENABLE_DEV_AUTH:
            try:
                return verify_dev_token(token)
            except Exception as error:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from error
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Firebase token")
