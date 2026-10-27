"""房间演员联机冒烟：四人入座 → 准备 → 开桌 → 出牌 → 聊天。

直接驱动 RoomActor（真实状态机 + 真实落库），用假 WebSocket 收集下行消息，
避免依赖真实网络，跑得快且稳定。
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.base import SessionLocal, init_db  # noqa: E402
from db.models import Room, User  # noqa: E402
from realtime.room import RoomActor  # noqa: E402
from schemas.rule import KongScore, RuleConfig, ToggleValue, TurnTimeout  # noqa: E402
from tools.seedPresets import install_presets  # noqa: E402


class FakeWS:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)

    def types(self) -> list[str]:
        return [message["type"] for message in self.messages]

    def last(self, msg_type: str) -> dict | None:
        for message in reversed(self.messages):
            if message["type"] == msg_type:
                return message
        return None


@pytest.fixture
def family():
    init_db()
    with SessionLocal() as session:
        install_presets(session)
        users = []
        for index, name in enumerate(["爸爸", "妈妈", "姐姐", "弟弟"]):
            username = f"member{index}"
            user = session.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(
                    username=username,
                    display_name=name,
                    password_hash="scrypt$1$1$1$x$y",
                    role="member",
                    color="#C9A063",
                )
                session.add(user)
                session.flush()
            users.append(user)
        code = f"T{users[0].id:05d}"
        room = session.scalar(select(Room).where(Room.code == code))
        if room is None:
            room = Room(
                code=code,
                name="周末家庭局",
                host_id=users[0].id,
                rule_template_id=None,
                rule_snapshot=RuleConfig().model_dump(),
                status="open",
            )
            session.add(room)
            session.commit()
        return users, room


async def build_actor(family, rule: RuleConfig | None = None):
    users, room = family
    config = rule or RuleConfig()
    actor = RoomActor(
        code=room.code,
        room_id=room.id,
        name=room.name,
        host_id=users[0].id,
        rule=config,
        rule_name="家庭标准",
        rule_snapshot=config.model_dump(),
    )
    sockets: dict[int, FakeWS] = {}
    for user in users:
        ws = FakeWS()
        sockets[user.id] = ws
        actor.attach(user.id, ws)
        actor.assign(user)
    return actor, users, sockets


async def test_four_players_start_discard_and_chat(family):
    actor, users, sockets = await build_actor(family)
    host = users[0]
    try:
        for user in users:
            await actor.handle(user.id, {"type": "seat.ready", "data": {}})
        assert all(slot.ready for slot in actor.slots if slot)

        await actor.handle(host.id, {"type": "game.start", "data": {}})
        snapshot = sockets[host.id].last("state.snapshot")
        assert snapshot is not None
        data = snapshot["data"]
        assert data["phase"] == "discard"
        assert len([seat for seat in data["seats"] if seat]) == 4
        assert len(data["hand"]) == 14  # 庄家 14 张
        assert data["turn"] == 0

        # 对手手牌绝不明文下发
        for seat in data["seats"]:
            if seat and seat["seat"] != 0:
                assert seat["hand_count"] == 13
        assert "hand" not in data["seats"][1]

        await actor.handle(users[1].id, {"type": "chat.send", "data": {"content": "开始了"}})
        chat = sockets[host.id].last("chat.message")
        assert chat is not None
        assert chat["data"]["content"] == "开始了"

        tile = data["hand"][0]
        await actor.handle(host.id, {"type": "game.action", "data": {"action": "discard", "tiles": [tile]}})
        assert any(
            message["type"] == "event.discarded" and message["data"]["tile"] == tile
            for message in sockets[host.id].messages
        )
    finally:
        actor._clear_timers()


async def test_non_host_cannot_start(family):
    actor, users, sockets = await build_actor(family)
    try:
        for user in users:
            await actor.handle(user.id, {"type": "seat.ready", "data": {}})
        await actor.handle(users[1].id, {"type": "game.start", "data": {}})
        error = sockets[users[1].id].last("error")
        assert error is not None
        assert error["data"]["code"] == "NOT_HOST"
    finally:
        actor._clear_timers()


async def test_start_requires_all_ready(family):
    actor, users, sockets = await build_actor(family)
    try:
        await actor.handle(users[0].id, {"type": "seat.ready", "data": {}})
        await actor.handle(users[0].id, {"type": "game.start", "data": {}})
        error = sockets[users[0].id].last("error")
        assert error is not None
        assert error["data"]["code"] == "NOT_READY"
    finally:
        actor._clear_timers()


async def test_turn_timeout_disabled_means_no_deadline(family):
    rule = RuleConfig(turn_timeout=TurnTimeout(enabled=False))
    actor, users, sockets = await build_actor(family, rule)
    try:
        for user in users:
            await actor.handle(user.id, {"type": "seat.ready", "data": {}})
        await actor.handle(users[0].id, {"type": "game.start", "data": {}})
        data = sockets[users[0].id].last("state.snapshot")["data"]
        assert data["deadline"] is None
        assert actor.turn_deadline is None
    finally:
        actor._clear_timers()


async def test_kong_score_disabled_reported_in_brief(family):
    rule = RuleConfig(
        kong_score=KongScore(enabled=False),
        ting_hint=ToggleValue(enabled=False),
    )
    actor, users, sockets = await build_actor(family, rule)
    try:
        brief = sockets[users[0].id].last("state.snapshot") if sockets[users[0].id].messages else None
        assert brief is None  # 还没推送过
        await actor.push_all()
        brief = sockets[users[0].id].last("state.snapshot")["data"]["room"]["rule_brief"]
        assert brief["kong_score"]["enabled"] is False
        assert brief["kong_score"]["exposed"] == 0
        assert brief["ting_hint"] is False
    finally:
        actor._clear_timers()


async def test_chat_rate_limit(family):
    actor, users, sockets = await build_actor(family)
    try:
        for _ in range(3):
            await actor.handle(users[0].id, {"type": "chat.send", "data": {"content": "在吗"}})
        await actor.handle(users[0].id, {"type": "chat.send", "data": {"content": "在吗"}})
        error = sockets[users[0].id].last("error")
        assert error is not None
        assert error["data"]["code"] == "CHAT_TOO_FAST"
    finally:
        actor._clear_timers()
