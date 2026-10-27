"""FastAPI 依赖：数据库会话、当前用户、管理员校验。"""

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from config.localSettings import settings
from common.securityCommon import decode_access_token
from db.base import get_session
from db.models import User


def db_session() -> Iterator[Session]:
    yield from get_session()


def _extract_token(authorization: str | None, token: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return token


def user_from_token(session: Session, token: str) -> User | None:
    payload = decode_access_token(token, settings.secret_key)
    if not payload:
        return None
    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        return None
    user = session.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    token: str | None = None,
    session: Session = Depends(db_session),
) -> User:
    raw = _extract_token(authorization, token)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录"
        )
    user = user_from_token(session, raw)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录"
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以做这个操作"
        )
    return user
