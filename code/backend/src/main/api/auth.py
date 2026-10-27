"""登录与个人信息。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.localSettings import settings
from main.deps import db_session, get_current_user
from common.securityCommon import create_access_token, hash_password, verify_password
from db.models import User
from schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role="admin" if user.is_admin else "member",
        color=user.color,
        is_active=user.is_active,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(db_session)) -> LoginResponse:
    user = session.scalar(select(User).where(User.username == payload.username.strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码不对"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="这个账号已被停用")
    token = create_access_token(
        user.id, user.username, user.role, settings.secret_key, settings.token_ttl_hours
    )
    return LoginResponse(token=token, user=to_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return to_user_out(user)


@router.post("/password", response_model=UserOut)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> UserOut:
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码不对")
    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能和原密码一样")
    target = session.get(User, user.id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    target.password_hash = hash_password(payload.new_password)
    session.commit()
    return to_user_out(target)


@router.get("/server-time")
def server_time() -> dict:
    return {"now": datetime.now(timezone.utc).isoformat()}
