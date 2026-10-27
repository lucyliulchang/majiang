"""FastAPI 依赖：JWT → 当前用户 → 家庭上下文。

S3 口径（01 §5、04 §2）：
  - JWT 由本系统签发：`sub` = loginID（字符串），`role` = admin/member；
  - `current_user` 解出 JWT 后回查 `USER_BASIC` 得到摘要（昵称/头像/角色名/启用标记），
    家庭信息不进 JWT；
  - 账号不存在 → 401；账号停用 → 403。

S4 口径（01 §6.1）：
  - `current_family` 从 **query `family_code` → path `family_code` → `mj_user_pref.lastFamilyID`**
    依次解析，再用 `familyService.assertMember` 校验成员关系；
  - 详情/操作类接口（room_id、template_id、skin_code）以资源自身的 familyID 为准，
    在 processor 内用 `familyService.assertMember` 校验，不经过本依赖；
  - 请求体里的 `family_code` 由路由直接传给 processor（依赖里读 body 会与 Pydantic 冲突）；
  - 停用家庭：成员仍可看家庭本身，资源类接口用 `current_active_family`（FAMILY_DISABLED）。

S5 口径：ORM 依赖、users 表映射与 Session 依赖已全部移除；所有端点与 WS 的身份
都是 loginID 字符串，家庭/房间/模板/战绩一律由 processor 层经 mysqlCommon 读写 MySQL。
"""

from dataclasses import dataclass

from fastapi import Depends, Header, Query, Request

from common.securityCommon import decode_access_token, role_from_payload
from processor import accountService, familyService

_UNAUTHORIZED_MESSAGE = "登录已失效，请重新登录"


@dataclass(frozen=True)
class CurrentUser:
    """登录用户摘要（只含 USER_BASIC 的安全列，绝不含 passwd）。"""

    login_id: str
    role: str
    role_name: str
    nick_name: str
    avatar_id: str
    active_flag: str

    @property
    def is_admin(self) -> bool:
        return self.role == accountService.ROLE_ADMIN

    @property
    def display_name(self) -> str:
        return self.nick_name or self.login_id

    def public(self) -> dict:
        return {
            "login_id": self.login_id,
            "nick_name": self.nick_name or self.login_id,
            "avatar_id": self.avatar_id,
            "role_name": self.role_name,
            "role": self.role,
            "active_flag": self.active_flag or "1",
        }


def _extract_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None
    return None


def current_user_from_token(token: str) -> CurrentUser | None:
    """校验 JWT 并回查 USER_BASIC；任何一环不成立都返回 None（由调用方映射 401）。"""
    payload = decode_access_token(token)
    if not payload:
        return None

    loginID = str(payload.get("sub") or "").strip()
    if not loginID:
        return None

    row = accountService.loadUserRow(loginID)
    if not row:
        return None

    return CurrentUser(
        login_id=loginID,
        role=role_from_payload(payload),
        role_name=str(row.get("roleName") or ""),
        nick_name=str(row.get("nickName") or ""),
        avatar_id=str(row.get("avatarID") or ""),
        active_flag=str(row.get("activeFlag") or "1"),
    )


def current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """REST 鉴权依赖：Authorization: Bearer <JWT>。

    失败一律 401 UNAUTHORIZED（04 §10）：篡改、过期、缺头、账号档案不存在都同一文案。
    """
    token = _extract_token(authorization)
    if not token:
        raise accountService.AccountServiceError("UNAUTHORIZED", _UNAUTHORIZED_MESSAGE, 401)

    user = current_user_from_token(token)
    if user is None:
        raise accountService.AccountServiceError("UNAUTHORIZED", _UNAUTHORIZED_MESSAGE, 401)
    if user.active_flag == "0":
        raise accountService.AccountServiceError("FORBIDDEN", "该账号已被停用", 403)
    return user


def require_admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """系统管理员（本系统角色 admin）。"""
    if not user.is_admin:
        raise accountService.AccountServiceError("FORBIDDEN", "没有权限执行该操作", 403)
    return user


# S4：系统管理员 = 全局角色 admin；与「家庭管理员（OWNER/ADMIN）」彻底分开
require_system_admin = require_admin


# ---------------------------------------------------------------- 家庭上下文（S4）


@dataclass(frozen=True)
class FamilyContext:
    """一次请求解析出的家庭上下文（01 §6.1）。

    `family` 是 `mj_family` 原始行（值为字符串），对外输出请用 `public()`。
    """

    login_id: str
    family_id: int
    family_code: str
    family_name: str
    member_role: str
    family_status: str
    family: dict

    @property
    def is_owner(self) -> bool:
        return self.member_role == familyService.ROLE_OWNER

    @property
    def is_family_admin(self) -> bool:
        return self.member_role in (familyService.ROLE_OWNER, familyService.ROLE_ADMIN)

    @property
    def is_enabled(self) -> bool:
        return self.family_status == familyService.FAMILY_ENABLED

    def require_admin(self) -> "FamilyContext":
        """在 processor/路由内就地要求家庭管理员身份（不额外依赖）。"""
        if not self.is_family_admin:
            raise familyService.FamilyServiceError(
                "NOT_FAMILY_ADMIN", "需要家庭管理员权限", 403
            )
        return self

    def public(self) -> dict:
        return familyService.familyOut(self.family, self.member_role)


def familyContextOf(
    loginID: str, familyCode: str, requireEnabled: bool = False
) -> FamilyContext:
    """非依赖版本：请求体 / 资源归属解析后使用（S5 的 room/rule/skin 会大量调用）。"""
    context = familyService.assertMember(loginID, familyCode, requireEnabled=requireEnabled)
    family = context["family"]
    return FamilyContext(
        login_id=loginID,
        family_id=context["familyID"],
        family_code=context["familyCode"],
        family_name=str(family.get("familyName") or ""),
        member_role=context["memberRole"],
        family_status=context["familyStatus"],
        family=family,
    )


def _resolveFamilyCode(request: Request, familyCode: str | None) -> str:
    """解析顺序：path `family_code` → query `family_code` → 空串（由调用方回落偏好）。

    路径里的家庭是「显式资源」，优先级必须高于 query，否则
    `GET /api/families/a?family_code=b` 会去校验 b 的成员关系而返回 a 的内容。
    """
    pathCode = str(request.path_params.get("family_code") or "").strip()
    if pathCode:
        return pathCode
    return (familyCode or "").strip()


def current_family(
    request: Request,
    family_code_query: str | None = Query(
        default=None, alias="family_code", description="家庭编码，缺省用当前家庭"
    ),
    user: CurrentUser = Depends(current_user),
) -> FamilyContext:
    """家庭上下文（允许停用家庭）：成员校验失败一律 403 NOT_FAMILY_MEMBER。

    查询参数对外仍是 `?family_code=`；Python 侧改名是为了避开与路径参数
    `/families/{family_code}` 的同名冲突（FastAPI 不允许路径参数声明成 Query）。
    """
    code = _resolveFamilyCode(request, family_code_query)
    if not code:
        code = familyService.currentFamilyCode(user.login_id) or ""
    if not code:
        raise familyService.FamilyServiceError(
            "NOT_FAMILY_MEMBER", "无权访问该家庭资源", 403
        )
    return familyContextOf(user.login_id, code)


def current_active_family(
    context: FamilyContext = Depends(current_family),
) -> FamilyContext:
    """资源类接口（房间/模板/皮肤）用：家庭停用 → 403 FAMILY_DISABLED。"""
    if not context.is_enabled:
        raise familyService.FamilyServiceError("FAMILY_DISABLED", "该家庭已停用", 403)
    return context


def require_family_admin(
    context: FamilyContext = Depends(current_family),
) -> FamilyContext:
    """家庭管理员（OWNER/ADMIN）；系统管理员不自动获得家庭内权限。"""
    return context.require_admin()
