"""JWT 签发与校验（HS256）。

口径（01 §5.5、04 §1）：
  - 载荷只有 `sub`（loginID，字符串）、`role`（本系统全局角色 admin/member）、`iat`、`exp`；
  - **不放家庭信息**，也不放昵称、头像等可变资料（一律回查 USER_BASIC）；
  - 口令由账号服务管理，本文件**不再包含任何口令哈希/校验逻辑**（S3 起移除 scrypt）。

密钥与 TTL 来自环境（SECRET_KEY / TOKEN_TTL_HOURS），默认值仅用于本地开发。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import jwt

_ALGO = "HS256"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"


def _resolve(secret: str | None) -> str:
    if secret:
        return secret
    from config.localSettings import settings  # 延迟导入，避免循环依赖

    return settings.secret_key


def _ttlHours(ttlHours: int | None) -> int:
    if ttlHours is not None:
        return int(ttlHours)
    from config.localSettings import settings

    return int(settings.token_ttl_hours)


def create_access_token(
    loginID: str, role: str, secret: str | None = None, ttlHours: int | None = None
) -> str:
    """签发 JWT：sub=loginID、role、iat/exp（epoch 秒）。"""
    subject = (loginID or "").strip()
    if not subject:
        raise ValueError("loginID 不能为空")

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": ROLE_ADMIN if role == ROLE_ADMIN else ROLE_MEMBER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=_ttlHours(ttlHours))).timestamp()),
    }
    return jwt.encode(payload, _resolve(secret), algorithm=_ALGO)


def decode_access_token(token: str, secret: str | None = None) -> dict[str, Any] | None:
    """校验并解出载荷；签名错误 / 过期 / 结构非法一律返回 None（由上层映射 401）。"""
    if not token:
        return None
    try:
        payload = jwt.decode(token, _resolve(secret), algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
    if not isinstance(payload, dict) or not payload.get("sub"):
        return None
    return payload


def role_from_payload(payload: Mapping[str, Any]) -> str:
    """从载荷取本系统角色，异常值一律回落 member（最小权限）。"""
    return ROLE_ADMIN if payload.get("role") == ROLE_ADMIN else ROLE_MEMBER
