"""家庭与成员的请求/响应模型（协议口径见 04 §3）。

字段一律 snake_case；协议里未列的可选字段（`status`）只在系统管理员场景使用。
"""

from pydantic import BaseModel


class FamilyOut(BaseModel):
    """04 §3 的 family；`member_role` 是**当前用户**在该家庭的角色。"""

    family_code: str
    family_name: str
    owner_login_id: str
    default_rule_family_code: str | None = None
    default_skin_code: str | None = None
    member_role: str = ""
    status: str = "ENABLED"
    sort_order: int = 0


class MemberOut(BaseModel):
    """04 §3 的 member。"""

    login_id: str
    nick_name: str = ""
    member_role: str = "MEMBER"
    member_status: str = "ACTIVE"
    joined_ymdhms: str = ""


class FamilyCreateRequest(BaseModel):
    """POST /api/families；`family_code` 不传则按名称生成（冲突重试）。"""

    family_code: str = ""
    family_name: str = ""


class FamilyUpdateRequest(BaseModel):
    """PATCH /api/families/{family_code}。

    `status` 是 S4 追加的运维口子（04 §3 未列）：仅系统管理员可改，
    用于验证「家庭停用后资源接口返回 FAMILY_DISABLED」。
    """

    family_name: str | None = None
    default_rule_family_code: str | None = None
    default_skin_code: str | None = None
    status: str | None = None


class MemberAddRequest(BaseModel):
    login_id: str = ""
    member_role: str = "MEMBER"


class MemberUpdateRequest(BaseModel):
    """PATCH /api/families/{family_code}/members/{login_id}。

    `nick_name` 是 owner/admin 代改成员的昵称（写 USER_BASIC.nickName），
    不能与「转让家长」「移出成员」在同一次请求里提交。
    """

    member_role: str | None = None
    member_status: str | None = None
    nick_name: str | None = None


class OkOut(BaseModel):
    ok: bool = True
