"""账号路由：登录 / 注册 / 找回口令 / 改密 / 登出 / 当前用户 / 服务时间。

全部账号动作都转发 contentHub 账号服务（acis），本地**不做口令校验**、不读写 users 表：
  - 登录成功：同步 USER_BASIC + 签发本地 JWT（载荷只有 sub/role/iat/exp）；
  - 注册成功、找回口令成功：只同步档案，**不签发 JWT**（04 §2.1-6、§2.2-4）；
  - 下游不可达：503 ACCOUNT_SERVICE_UNAVAILABLE，不产生半登录状态。

错误码与提示统一由 processor/accountService 抛出 AccountServiceError，app.py 负责转成
{"detail": ..., "code": ...}（04 §1）。
"""

from fastapi import APIRouter, Depends

from common import miscCommon as misc
from common.securityCommon import create_access_token
from main.deps import CurrentUser, current_user
from processor import accountService, familyService
from schemas.auth import (
    AuthOptionsResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OkResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ServerTimeResponse,
    UserOut,
    VerifyCodeRequest,
    VerifyCodeResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    result = accountService.login(payload.login_id, payload.passwd)
    token = create_access_token(result["login_id"], result["role"])
    # 家庭不进 JWT（01 §5.5-3）：每次登录实时取，并补写 pref.lastFamilyID（04 §2）
    families = familyService.listMyFamilies(result["login_id"])
    currentFamilyCode = familyService.ensureDefaultFamily(result["login_id"])
    return LoginResponse(
        token=token,
        user=UserOut(**{key: result[key] for key in UserOut.model_fields}),
        families=families,
        current_family_code=currentFamilyCode,
    )


@router.post("/logout", response_model=OkResponse)
def logout(user: CurrentUser = Depends(current_user)) -> OkResponse:
    # A5A0 尽力而为：账号服务不可达也必须返回 ok（本地 JWT 由前端丢弃）
    accountService.logout(user.login_id)
    return OkResponse(ok=True)


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser = Depends(current_user)) -> MeResponse:
    """当前用户 + 我的家庭 + 当前家庭（S4：家庭列表不再是占位空数组）。"""
    families = familyService.listMyFamilies(user.login_id)
    currentFamilyCode = familyService.ensureDefaultFamily(user.login_id)
    return MeResponse(
        user=UserOut(**user.public()),
        families=families,
        current_family_code=currentFamilyCode,
    )


@router.post("/password", response_model=OkResponse)
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser = Depends(current_user)
) -> OkResponse:
    accountService.changePassword(user.login_id, payload.old_passwd, payload.new_passwd)
    return OkResponse(ok=True)


@router.get("/server-time", response_model=ServerTimeResponse)
def server_time() -> ServerTimeResponse:
    # 对外一律 RFC3339（+08:00），与 04 §1 时间口径一致
    return ServerTimeResponse(now=misc.nowDb().isoformat(timespec="seconds"))


@router.post("/verify-code", response_model=VerifyCodeResponse)
def verify_code(payload: VerifyCodeRequest) -> VerifyCodeResponse:
    result = accountService.sendVerifyCode(payload.login_id, payload.scene)
    return VerifyCodeResponse(**result)


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest) -> RegisterResponse:
    result = accountService.register(
        payload.login_id, payload.passwd, payload.verify_code, payload.nick_name
    )
    return RegisterResponse(**result)


@router.post("/password/reset", response_model=OkResponse)
def reset_password(payload: ResetPasswordRequest) -> OkResponse:
    accountService.resetPassword(payload.login_id, payload.verify_code, payload.new_passwd)
    return OkResponse(ok=True)


@router.get("/options", response_model=AuthOptionsResponse)
def options() -> AuthOptionsResponse:
    return AuthOptionsResponse(**accountService.options())
