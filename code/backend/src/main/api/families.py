"""家庭与成员路由（04 §3，8 个端点）。

分层（01 §2）：
  - 本文件只做「解析参数 → JWT/家庭上下文 → 调 familyService → 映射响应模型」；
  - 权限判断（成员 / 家庭管理员 / 系统管理员）不在路由里写 if，统一走 deps 与 service；
  - 错误码与中文提示由 familyService 抛 FamilyServiceError，app.py 统一转错误体。
"""

from fastapi import APIRouter, Depends, Request

from main.deps import (
    CurrentUser,
    FamilyContext,
    current_family,
    current_user,
    require_family_admin,
)
from processor import familyService
from schemas.family import (
    FamilyCreateRequest,
    FamilyOut,
    FamilyUpdateRequest,
    MemberAddRequest,
    MemberOut,
    MemberUpdateRequest,
    OkOut,
)

router = APIRouter(prefix="/families", tags=["families"])


def _clientIP(request: Request) -> str:
    return request.client.host if request.client else ""


# ---------------------------------------------------------------- 家庭


@router.get("", response_model=list[FamilyOut])
def list_families(user: CurrentUser = Depends(current_user)) -> list[FamilyOut]:
    """我的家庭（join 成员表，只返回 ACTIVE 成员关系）。"""
    return [FamilyOut(**item) for item in familyService.listMyFamilies(user.login_id)]


@router.post("", response_model=FamilyOut)
def create_family(
    payload: FamilyCreateRequest,
    request: Request,
    user: CurrentUser = Depends(current_user),
) -> FamilyOut:
    """创建家庭：创建者自动成为 OWNER，并写 pref.lastFamilyID。

    同一 `family_code` 重复创建固定返回 409 `FAMILY_CODE_EXISTS`。
    """
    return FamilyOut(
        **familyService.createFamily(
            user.login_id,
            payload.family_name,
            payload.family_code,
            clientIP=_clientIP(request),
        )
    )


@router.get("/{family_code}", response_model=FamilyOut)
def get_family(context: FamilyContext = Depends(current_family)) -> FamilyOut:
    """家庭详情：非成员/不存在都返回 403 NOT_FAMILY_MEMBER（不泄露资源是否存在）。"""
    return FamilyOut(**context.public())


@router.patch("/{family_code}", response_model=FamilyOut)
def update_family(
    payload: FamilyUpdateRequest,
    request: Request,
    context: FamilyContext = Depends(current_family),
    user: CurrentUser = Depends(current_user),
) -> FamilyOut:
    """更新家庭：owner/admin；`status` 仅系统管理员可改。"""
    context.require_admin()
    return FamilyOut(
        **familyService.updateFamily(
            user.login_id,
            context.family_code,
            familyName=payload.family_name,
            defaultRuleFamilyCode=payload.default_rule_family_code,
            defaultSkinCode=payload.default_skin_code,
            familyStatus=payload.status,
            clientIP=_clientIP(request),
            operatorIsSystemAdmin=user.is_admin,
        )
    )


# ---------------------------------------------------------------- 成员


@router.get("/{family_code}/members", response_model=list[MemberOut])
def list_members(
    include_left: bool = False,
    context: FamilyContext = Depends(current_family),
) -> list[MemberOut]:
    """家庭成员列表：成员可读；`include_left=1` 时带上已退出成员。"""
    rows = familyService.listMembers(context.login_id, context.family_code, includeLeft=include_left)
    return [MemberOut(**row) for row in rows]


@router.post("/{family_code}/members", response_model=MemberOut)
def add_member(
    payload: MemberAddRequest,
    request: Request,
    context: FamilyContext = Depends(require_family_admin),
    user: CurrentUser = Depends(current_user),
) -> MemberOut:
    """添加成员：owner/admin；账号须存在于账号服务（AIA0）。"""
    return MemberOut(
        **familyService.addMember(
            user.login_id,
            context.family_code,
            payload.login_id,
            payload.member_role,
            clientIP=_clientIP(request),
            operatorIsSystemAdmin=user.is_admin,
        )
    )


@router.patch("/{family_code}/members/{login_id}", response_model=MemberOut)
def update_member(
    login_id: str,
    payload: MemberUpdateRequest,
    request: Request,
    context: FamilyContext = Depends(require_family_admin),
    user: CurrentUser = Depends(current_user),
) -> MemberOut:
    """更新成员：owner/admin；`member_role=OWNER` 即转让（同一事务，owner 唯一）。"""
    return MemberOut(
        **familyService.updateMember(
            user.login_id,
            context.family_code,
            login_id,
            memberRole=payload.member_role,
            memberStatus=payload.member_status,
            clientIP=_clientIP(request),
            operatorIsSystemAdmin=user.is_admin,
        )
    )


@router.delete("/{family_code}/members/{login_id}", response_model=OkOut)
def remove_member(
    login_id: str,
    request: Request,
    context: FamilyContext = Depends(current_family),
    user: CurrentUser = Depends(current_user),
) -> OkOut:
    """移出成员：owner/admin 可移他人，成员可自行退出；owner 不可被移除。"""
    familyService.removeMember(
        user.login_id,
        context.family_code,
        login_id,
        clientIP=_clientIP(request),
        operatorIsSystemAdmin=user.is_admin,
    )
    return OkOut(ok=True)
