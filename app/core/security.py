import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, token_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "access", "ver": token_version},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(subject: str, token_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "refresh", "ver": token_version},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(
    token: str, expected_type: Literal["access", "refresh"]
) -> Optional[dict]:
    """
    Decode and validate a JWT.

    Returns {"sub": user_id, "ver": token_version} or None on any failure.
    Validates the `type` claim so access tokens cannot be used as refresh
    tokens and vice versa.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        sub = payload.get("sub")
        ver = payload.get("ver")
        if sub is None or ver is None:
            return None
        return {"sub": str(sub), "ver": int(ver)}
    except JWTError:
        return None


def generate_secure_token() -> str:
    """Cryptographically secure URL-safe random token (for email / password reset)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """One-way SHA-256 hash for storing tokens in the DB.

    Even if the tokens table is compromised, the raw token cannot be recovered.
    """
    return hashlib.sha256(token.encode()).hexdigest()
