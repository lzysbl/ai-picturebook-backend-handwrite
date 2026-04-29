"""User routes for registration, login, profile, and password recovery."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.user import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginResponseData,
    ResetPasswordRequest,
    UserInfo,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.services.user_service import (
    authenticate_user,
    change_password,
    create_user,
    get_user_by_id,
    issue_password_reset_token,
    reset_password_with_token,
)
from app.utils.rate_limiter import enforce_rate_limit
from app.utils.security import JWTError, create_access_token, decode_access_token

router = APIRouter(prefix="/api/users", tags=["Users"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


def _should_expose_reset_token() -> bool:
    return settings.debug or settings.app_env.lower() != "production"


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录状态无效，请重新登录",
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc

    user = await get_user_by_id(db, int(user_id))
    if not user:
        raise credentials_error
    return user


@router.post("/register", response_model=ApiResponse)
async def register(
    payload: UserRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await enforce_rate_limit(
        request=request,
        action="users:register",
        limit=settings.rate_limit_register_limit,
        window_seconds=settings.rate_limit_register_window_seconds,
    )

    try:
        user = await create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        if "72 bytes" in str(exc):
            raise HTTPException(
                status_code=400,
                detail="密码过长：最大 72 字节（英文约 72 个字符，中文约 24 个字符）",
            ) from exc
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试") from exc

    return ApiResponse(
        success=True,
        message="注册成功",
        data=UserInfo.model_validate(user).model_dump(),
    )


@router.post("/login", response_model=ApiResponse)
async def login(
    payload: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await enforce_rate_limit(
        request=request,
        action="users:login",
        limit=settings.rate_limit_login_limit,
        window_seconds=settings.rate_limit_login_window_seconds,
    )

    user = await authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名/邮箱或密码错误")

    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    login_data = LoginResponseData(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo.model_validate(user),
    )
    return ApiResponse(success=True, message="登录成功", data=login_data.model_dump())


@router.post("/forgot-password", response_model=ApiResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await enforce_rate_limit(
        request=request,
        action="users:forgot_password",
        limit=settings.rate_limit_register_limit,
        window_seconds=settings.rate_limit_register_window_seconds,
    )

    token = await issue_password_reset_token(db, payload.email, settings.password_reset_token_expire_minutes)
    data = None
    if token and _should_expose_reset_token():
        data = {
            "reset_token": token,
            "reset_url": f"/ui/reset-password?token={token}",
            "expires_minutes": settings.password_reset_token_expire_minutes,
        }
    return ApiResponse(
        success=True,
        message="如果该邮箱已注册，系统已生成密码重置链接",
        data=data,
    )


@router.post("/reset-password", response_model=ApiResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await enforce_rate_limit(
        request=request,
        action="users:reset_password",
        limit=settings.rate_limit_login_limit,
        window_seconds=settings.rate_limit_login_window_seconds,
    )

    success = await reset_password_with_token(db, payload.token, payload.password)
    if not success:
        raise HTTPException(status_code=400, detail="重置链接无效或已过期")
    return ApiResponse(success=True, message="密码重置成功，请重新登录", data=None)


@router.post("/change-password", response_model=ApiResponse)
async def change_password_api(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ApiResponse:
    try:
        await change_password(db, current_user, payload.old_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="密码修改成功", data=None)


@router.get("/me", response_model=ApiResponse)
async def get_me(current_user=Depends(get_current_user)) -> ApiResponse:
    return ApiResponse(
        success=True,
        message="获取成功",
        data=UserInfo.model_validate(current_user).model_dump(),
    )
