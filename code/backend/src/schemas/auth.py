"""账号相关的请求/响应模型（协议口径见 04 §2）。

字段一律 snake_case；`login_id` 兼容旧字段 `username`，`passwd` 兼容旧字段 `password`
（仅登录接口，便于前端从自建账号平滑过渡）。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Role = Literal["admin", "member"]
Scene = Literal["register", "reset_password"]


class LoginRequest(BaseModel):
    login_id: str = ""
    passwd: str = ""
    # 过渡兼容：老前端提交 username/password
    username: str = Field(default="", exclude=True)
    password: str = Field(default="", exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _mergeLegacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        merged = dict(data)
        if not merged.get("login_id") and merged.get("username"):
            merged["login_id"] = merged["username"]
        if not merged.get("passwd") and merged.get("password"):
            merged["passwd"] = merged["password"]
        return merged


class UserOut(BaseModel):
    """04 §2 的 user 摘要（不含口令、不含家庭）。"""

    login_id: str
    nick_name: str
    avatar_id: str = ""
    role_name: str = ""
    role: Role = "member"
    active_flag: str = "1"


class FamiliesOut(BaseModel):
    """家庭列表占位：S4 落地前恒为空数组，字段形状不变。"""

    families: list[dict] = Field(default_factory=list)
    current_family_code: str | None = None


class LoginResponse(BaseModel):
    token: str
    user: UserOut
    families: list[dict] = Field(default_factory=list)
    current_family_code: str | None = None


class MeResponse(BaseModel):
    user: UserOut
    families: list[dict] = Field(default_factory=list)
    current_family_code: str | None = None


class ChangePasswordRequest(BaseModel):
    old_passwd: str = ""
    new_passwd: str = ""


class VerifyCodeRequest(BaseModel):
    login_id: str = ""
    scene: Scene = "register"


class RegisterRequest(BaseModel):
    login_id: str = ""
    passwd: str = ""
    verify_code: str = ""
    nick_name: str = ""


class ResetPasswordRequest(BaseModel):
    login_id: str = ""
    verify_code: str = ""
    new_passwd: str = ""


class RegisterResponse(BaseModel):
    ok: bool = True
    login_id: str


class OkResponse(BaseModel):
    ok: bool = True


class VerifyCodeResponse(BaseModel):
    ok: bool = True
    cooldown_seconds: int = 60
    expire_seconds: int = 600


class AuthOptionsResponse(BaseModel):
    register_enabled: bool
    password_reset_enabled: bool
    verify_code_cooldown_seconds: int = 60


class ServerTimeResponse(BaseModel):
    now: str
