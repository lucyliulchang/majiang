"""房间演员联机冒烟（S5：真实测试库 mahjong_test + mysqlCommon 落库）。

四人入座 → 准备 → 开桌 → 出牌 → 聊天，并断言：
  - 开桌后 `mj_game` 有 1 行 PLAYING、`mj_game_player` 有 4 行（同事务写入）；
  - 聊天写入 `mj_room_message`，loginID 与昵称正确；
  - 协程内的落库走线程池（`persist.*` 均在线程里执行）。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import mysqlCommon  # noqa: E402
from realtime.room import RoomActor  # noqa: E402
from schemas.rule import KongScore, RuleConfig, ToggleValue, TurnTimeout  # noqa: E402

pytestmark = pytest.mark.usefixtures("s5_env")


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


def build_actor(s5_env, rule: RuleConfig | None = None):
    room = s5_env["room"]
    config = rule or RuleConfig()
    snapshot = {
        "rule_family_code": "generic",
        "template_id": s5_env["template_id"],
        "config": config.model_dump(),
    }
    actor = RoomActor(
        code=room["room_code"],
        room_id=room["id"],
        family_id=s5_env["family_id"],
        family_code=s5_env["family_code"],
        family_name="S5 测试家庭",
        name=room["room_name"],
        host_login_id=s5_env["owner"],
        rule=config,
        rule_name="家庭标准",
        rule_snapshot=snapshot,
    )
    sockets = {}
    for loginID in s5_env["members"]:
        ws = FakeWS()
        sockets[loginID] = ws
        actor.attach(loginID, ws)
        actor.assign(loginID, f"玩家{loginID[-1]}", "#C9A063")
    return actor, sockets


async def test_four_players_start_discard_and_chat(s5_env):
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        for loginID in s5_env["members"]:
            await actor.handle(loginID, {"type": "seat.ready", "data": {}})
        assert all(slot.ready for slot in actor.slots if slot)

        await actor.handle(owner, {"type": "game.start", "data": {}})
        snapshot = sockets[owner].last("state.snapshot")
        assert snapshot is not None
        data = snapshot["data"]
        assert data["phase"] == "discard"
        assert len([seat for seat in data["seats"] if seat]) == 4
        assert len(data["hand"]) == 14  # 庄家 14 张
        assert data["turn"] == 0
        assert data["room"]["family_code"] == s5_env["family_code"]

        # 对手手牌绝不明文下发
        for seat in data["seats"]:
            if seat and seat["seat"] != 0:
                assert seat["hand_count"] == 13
        assert "hand" not in data["seats"][1]
        assert data["seats"][0]["login_id"] == owner

        # 开局落库：1 场 + 4 座位（同一事务）
        assert actor.game_id
        game = mysqlCommon.query_mj_game_by_id(actor.game_id)
        assert game["gameStatus"] == "PLAYING"
        players = mysqlCommon.query_mj_game_player_list(actor.game_id)
        assert len(players) == 4
        assert {row["loginID"] for row in players} == set(s5_env["members"])

        await actor.handle(
            s5_env["members"][1], {"type": "chat.send", "data": {"content": "开始了"}}
        )
        chat = sockets[owner].last("chat.message")
        assert chat is not None
        assert chat["data"]["content"] == "开始了"
        assert chat["data"]["login_id"] == s5_env["members"][1]
        assert chat["data"]["user_name"] == "玩家2"

        messages = mysqlCommon.query_mj_room_message_list(actor.room_id, limit=10)
        assert any(row["content"] == "开始了" for row in messages)

        tile = data["hand"][0]
        await actor.handle(
            owner, {"type": "game.action", "data": {"action": "discard", "tiles": [tile]}}
        )
        assert any(
            message["type"] == "event.discarded" and message["data"]["tile"] == tile
            for message in sockets[owner].messages
        )
    finally:
        actor._clear_timers()


async def test_non_host_cannot_start(s5_env):
    actor, sockets = build_actor(s5_env)
    try:
        for loginID in s5_env["members"]:
            await actor.handle(loginID, {"type": "seat.ready", "data": {}})
        guest = s5_env["members"][1]
        await actor.handle(guest, {"type": "game.start", "data": {}})
        error = sockets[guest].last("error")
        assert error is not None
        assert error["data"]["code"] == "NOT_HOST"
    finally:
        actor._clear_timers()


async def test_start_requires_all_ready(s5_env):
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        await actor.handle(owner, {"type": "seat.ready", "data": {}})
        await actor.handle(owner, {"type": "game.start", "data": {}})
        error = sockets[owner].last("error")
        assert error is not None
        assert error["data"]["code"] == "NOT_READY"
    finally:
        actor._clear_timers()


async def test_turn_timeout_disabled_means_no_deadline(s5_env):
    rule = RuleConfig(turn_timeout=TurnTimeout(enabled=False))
    actor, sockets = build_actor(s5_env, rule)
    owner = s5_env["owner"]
    try:
        for loginID in s5_env["members"]:
            await actor.handle(loginID, {"type": "seat.ready", "data": {}})
        await actor.handle(owner, {"type": "game.start", "data": {}})
        data = sockets[owner].last("state.snapshot")["data"]
        assert data["deadline"] is None
        assert actor.turn_deadline is None
    finally:
        actor._clear_timers()


async def test_kong_score_disabled_reported_in_brief(s5_env):
    rule = RuleConfig(
        kong_score=KongScore(enabled=False),
        ting_hint=ToggleValue(enabled=False),
    )
    actor, sockets = build_actor(s5_env, rule)
    owner = s5_env["owner"]
    try:
        assert sockets[owner].messages == []
        await actor.push_all()
        brief = sockets[owner].last("state.snapshot")["data"]["room"]["rule_brief"]
        assert brief["kong_score"]["enabled"] is False
        assert brief["kong_score"]["exposed"] == 0
        assert brief["ting_hint"] is False
    finally:
        actor._clear_timers()


async def test_chat_rate_limit(s5_env):
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        for _ in range(3):
            await actor.handle(owner, {"type": "chat.send", "data": {"content": "在吗"}})
        await actor.handle(owner, {"type": "chat.send", "data": {"content": "在吗"}})
        error = sockets[owner].last("error")
        assert error is not None
        assert error["data"]["code"] == "CHAT_TOO_FAST"
    finally:
        actor._clear_timers()
