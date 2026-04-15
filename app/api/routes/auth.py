from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import limiter
from app.core.security import create_access_token, decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import (
    confirm_password_reset,
    login_user,
    logout_user,
    register_user,
    request_password_reset,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
@limiter.limit("3/minute")
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await register_user(data, db)
    return {
        "message": "Регистрация прошла успешно. Проверьте почту для подтверждения аккаунта.",
        "user_id": user.id,
    }


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    tokens = await login_user(data, db)
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
    )
    return {"access_token": tokens["access_token"]}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    payload = decode_token(refresh_token, "refresh")
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if user.token_version != payload["ver"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    return {"access_token": create_access_token(str(user.id), user.token_version)}


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Server-side invalidation: bump token_version so all issued tokens
    # (access + refresh) become invalid immediately.
    await logout_user(current_user.id, db)
    response.delete_cookie("refresh_token", httponly=True, secure=True, samesite="strict")
    return {"message": "Logged out"}


@router.post("/verify-email", status_code=200)
async def verify_email_route(
    data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    await verify_email(data.token, db)
    return {"message": "Email подтверждён"}


@router.post("/forgot-password", status_code=200)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await request_password_reset(data.email, db)
    # Always 200 regardless of whether the email exists — prevents enumeration.
    return {"message": "Если аккаунт существует, письмо со сбросом пароля отправлено"}


@router.post("/reset-password", status_code=200)
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await confirm_password_reset(data.token, data.new_password, db)
    return {"message": "Пароль изменён. Войдите заново."}
