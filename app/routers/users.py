"""用户路由：注册、登录、获取当前用户。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.user import LoginResponseData, UserInfo, UserLoginRequest, UserRegisterRequest
from app.services.user_service import authenticate_user, create_user, get_user_by_id
from app.utils.security import JWTError, create_access_token, decode_access_token

router = APIRouter(prefix="/api/users", tags=["Users"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """通用鉴权依赖：解析 token 并返回当前用户。"""

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
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """用户注册接口。"""

    try:
        user = await create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApiResponse(
        success=True,
        message="注册成功",
        data=UserInfo.model_validate(user).model_dump(),
    )


@router.post("/login", response_model=ApiResponse)
async def login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """用户登录接口。"""

    user = await authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    login_data = LoginResponseData(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo.model_validate(user),
    )
    return ApiResponse(success=True, message="登录成功", data=login_data.model_dump())


@router.get("/me", response_model=ApiResponse)
async def get_me(current_user=Depends(get_current_user)) -> ApiResponse:
    """获取当前登录用户信息。"""

    return ApiResponse(
        success=True,
        message="获取成功",
        data=UserInfo.model_validate(current_user).model_dump(),
    )
