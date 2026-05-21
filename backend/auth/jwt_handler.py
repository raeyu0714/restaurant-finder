from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def create_access_token(secret_key: str, algorithm: str, data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str) -> dict:
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的身份令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


def make_auth_dependency(secret_key: str, algorithm: str):
    """Returns a FastAPI dependency that validates the JWT from the Bearer header."""
    def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
        return decode_token(token, secret_key, algorithm)
    return get_current_user
