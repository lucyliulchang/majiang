"""房间相关的请求/响应模型（04 §6）。

字段口径与 04 逐字一致：`room_code` / `family_code` / `host_login_id` / `rule_family_code`；
`player_count` 与 `spectator_count` 是内存态实时值（房态不落库）。
"""

from pydantic import BaseModel, Field


class RoomCreateRequest(BaseModel):
    family_code: str = ""
    room_name: str = Field(min_length=1, max_length=64)
    template_id: int


class RoomOut(BaseModel):
    id: int
    room_code: str
    family_code: str
    room_name: str
    host_login_id: str
    host_name: str
    template_id: int | None = None
    rule_name: str
    rule_family_code: str
    status: str
    player_count: int = 0
    spectator_count: int = 0
    created_at: str


class SpectateOut(BaseModel):
    limit_per_seat: int = 10
    viewer_counts: list[int] = Field(default_factory=lambda: [0, 0, 0, 0])
    available: bool = True


class RoomJoinCheck(BaseModel):
    room_code: str
    room_name: str
    host_name: str
    rule_name: str
    rule_family_code: str
    status: str
    player_count: int = 0
    can_join: bool = True
    spectate: SpectateOut = Field(default_factory=SpectateOut)


class ChatMessageOut(BaseModel):
    id: int
    room_id: int
    login_id: str | None = None
    user_name: str
    kind: str
    content: str
    created_at: str
