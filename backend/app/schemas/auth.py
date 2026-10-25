"""账号相关的请求/响应模型。"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["admin", "member"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: Role
    color: str
    is_active: bool


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    display_name: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    role: Role = "member"
    color: str = "#C9A063"

    @field_validator("username")
    @classmethod
    def _username_ok(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError("账号只能包含字母、数字、下划线和连字符")
        return cleaned

    @field_validator("color")
    @classmethod
    def _color_ok(cls, value: str) -> str:
        if not value.startswith("#") or len(value) not in (4, 7):
            raise ValueError("颜色请使用 #RGB 或 #RRGGBB 格式")
        return value


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=32)
    role: Role | None = None
    color: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
