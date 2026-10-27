"""房间相关的请求/响应模型。"""

from pydantic import BaseModel, Field


class RoomCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    rule_template_id: int


class RoomOut(BaseModel):
    id: int
    code: str
    name: str
    host_id: int
    host_name: str
    rule_template_id: int | None
    rule_name: str
    status: str
    created_at: str
    player_count: int = 0


class RoomJoinCheck(BaseModel):
    code: str
    name: str
    host_name: str
    rule_name: str
    status: str
    player_count: int


class ChatMessageOut(BaseModel):
    id: int
    room_id: int
    user_id: int | None
    user_name: str
    kind: str
    content: str
    created_at: str
