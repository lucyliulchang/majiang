"""WebSocket 消息契约。

统一信封：{"v":1,"type":"...","seq":n,"ts":1700000000,"data":{...}}
"""

import time
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

PROTOCOL_VERSION = 1

ClientType = Literal[
    "auth",
    "room.join",
    "room.leave",
    "seat.ready",
    "game.start",
    "game.finish",
    "game.action",
    "chat.send",
    "state.resync",
    "ping",
]

ActionType = Literal["discard", "chow", "pong", "kong", "hu", "pass"]


class Envelope(BaseModel):
    v: int = PROTOCOL_VERSION
    type: ClientType | str
    seq: int | None = None
    ts: int = Field(default_factory=lambda: int(time.time()))
    data: dict[str, Any] = Field(default_factory=dict)


class GameActionData(BaseModel):
    action: ActionType
    tiles: list[int] = Field(default_factory=list)
    # 杠的类型：exposed（明杠）/ hidden（暗杠）/ added（补杠）
    kong_kind: str | None = None


class ChatSendData(BaseModel):
    content: str = Field(min_length=1, max_length=200)


class ErrorData(BaseModel):
    code: str
    message: str


def make_message(msg_type: str, data: dict[str, Any] | None = None, seq: int | None = None) -> dict:
    payload: dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": msg_type,
        "ts": int(time.time()),
        "data": data or {},
    }
    if seq is not None:
        payload["seq"] = seq
    return payload


def parse_envelope(raw: Any) -> Envelope | None:
    try:
        return Envelope.model_validate(raw)
    except ValidationError:
        return None
