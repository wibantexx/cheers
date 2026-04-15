from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.email_service import send_password_reset_email, send_verification_email

_RESET_TOKEN_TTL_HOURS = 1
_VERIFY_TOKEN_TTL_HOURS = 24

# Pre-hashed dummy used in login to keep response time constant whether or
# not a matching email exists, preventing user-enumeration via timing.
_DUMMY_HASH: str = hash_password("__cheers_timing_protection_dummy__")


async def register_user(data: RegisterRequest, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        age=data.age,
        is_verified=False,
    )
    db.add(user)
    await db.flush()  # populate user.id without committing yet

    raw_token = generate_secure_token()
    verification = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=_VERIFY_TOKEN_TTL_HOURS),
    )
    db.add(verification)
    await db.commit()
    await db.refresh(user)

    await send_verification_email(user.email, raw_token)
    return user


async def login_user(data: LoginRequest, db: AsyncSession) -> dict:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        # Always run bcrypt to prevent timing-based user enumeration.
        verify_password(data.password, _DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox.",
        )

    return {
        "access_token": create_access_token(str(user.id), user.token_version),
        "refresh_token": create_refresh_token(str(user.id), user.token_version),
    }


async def logout_user(user_id: str, db: AsyncSession) -> None:
    """Bump token_version to instantly invalidate all issued tokens for this user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.token_version += 1
        await db.commit()


async def verify_email(token: str, db: AsyncSession) -> None:
    token_hash = hash_token(token)
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if not record or record.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    record.used = True
    result = await db.execute(select(User).where(User.id == record.user_id))
    user = result.scalar_one()
    user.is_verified = True
    await db.commit()


async def request_password_reset(email: str, db: AsyncSession) -> None:
    """
    Always returns without error to prevent user enumeration.
    Only sends an email when the account exists.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return

    # Invalidate any outstanding reset tokens for this user.
    existing = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,  # noqa: E712
        )
    )
    for old in existing.scalars().all():
        old.used = True

    raw_token = generate_secure_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=_RESET_TOKEN_TTL_HOURS),
    )
    db.add(reset_token)
    await db.commit()

    await send_password_reset_email(user.email, raw_token)


async def confirm_password_reset(token: str, new_password: str, db: AsyncSession) -> None:
    token_hash = hash_token(token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    # Same error for "not found", "already used", and "expired" — no info leak.
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )

    if not record or record.used:
        raise invalid

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise invalid

    record.used = True  # one-time use

    result = await db.execute(select(User).where(User.id == record.user_id))
    user = result.scalar_one()
    user.hashed_password = hash_password(new_password)
    user.token_version += 1  # log out all existing sessions

    await db.commit()
