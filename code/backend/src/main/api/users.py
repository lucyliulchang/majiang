"""家庭成员管理（管理员）。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from main.api.auth import to_user_out
from main.deps import db_session, require_admin
from common.securityCommon import hash_password
from db.models import User
from schemas.auth import UserCreateRequest, UserOut, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_admin), session: Session = Depends(db_session)
) -> list[UserOut]:
    rows = session.scalars(select(User).order_by(User.id)).all()
    return [to_user_out(row) for row in rows]


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreateRequest,
    _: User = Depends(require_admin),
    session: Session = Depends(db_session),
) -> UserOut:
    exists = session.scalar(select(User).where(User.username == payload.username))
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="这个账号已经存在了")
    user = User(
        username=payload.username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        color=payload.color,
    )
    session.add(user)
    session.commit()
    return to_user_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    admin: User = Depends(require_admin),
    session: Session = Depends(db_session),
) -> UserOut:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.role is not None:
        if user.id == admin.id and payload.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="不能取消自己的管理员身份"
            )
        user.role = payload.role
    if payload.color is not None:
        user.color = payload.color
    if payload.is_active is not None:
        if user.id == admin.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用自己"
            )
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    session.commit()
    return to_user_out(user)
