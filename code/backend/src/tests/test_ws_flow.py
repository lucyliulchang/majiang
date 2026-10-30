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
from realtime import persist  # noqa: E402
from realtime.room import RoomActor  # noqa: E402
from game.families.generic.config import (  # noqa: E402
    KongScore,
    RuleConfig,
    ToggleValue,
    TurnTimeout,
)

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
        # 抽座后东位（座位 0）即庄家：庄家 14 张、闲家各 13 张（03 §3.4/§3.5）
        selfSeat = data["self_seat"]
        assert data["dealer_seat"] == 0
        assert data["seats"][0]["hand_count"] == 14
        assert data["seats"][0]["is_dealer"] is True
        for seat in data["seats"][1:]:
            assert seat["hand_count"] == 13
            assert seat["is_dealer"] is False
        assert len(data["hand"]) == (14 if selfSeat == 0 else 13)
        assert data["turn"] == 0  # 首轮庄家直接出牌
        assert data["room"]["family_code"] == s5_env["family_code"]

        # 对手手牌绝不明文下发
        for seat in data["seats"]:
            if seat["seat"] != selfSeat:
                assert "hand" not in seat
        assert data["seats"][selfSeat]["login_id"] == owner

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

        # 出牌人是当前 turn（抽座后未必是房主）
        turnSeat = data["turn"]
        turnLogin = actor.slots[turnSeat].login_id
        tile = next(
            index for index, count in enumerate(actor.engine.seats[turnSeat].counts) if count > 0
        )
        await actor.handle(
            turnLogin, {"type": "game.action", "data": {"action": "discard", "tiles": [tile]}}
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


async def test_host_can_end_game_early(s5_env):
    """开桌的人可以提前收场：已打完的局保留，未结算的一局作废，这桌随即关房。"""
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        for loginID in s5_env["members"]:
            await actor.handle(loginID, {"type": "seat.ready", "data": {}})
        await actor.handle(owner, {"type": "game.start", "data": {}})
        gameID = actor.game_id
        assert gameID
        ownerSeat = actor.seat_of_login(owner)

        await actor.handle(owner, {"type": "game.finish", "data": {}})

        finished = sockets[owner].last("event.game_finished")
        assert finished is not None
        assert finished["data"]["aborted"] is True
        assert finished["data"]["ended_by_seat"] == ownerSeat
        assert len(finished["data"]["scores"]) == 4

        # 房态清空：不会留着半局没人能动的牌（收尾后房间状态统一是 closed）
        assert actor.status == "closed"
        assert actor.finalized is True
        assert actor.engine is None
        assert all(not slot.ready for slot in actor.slots if slot)

        # 收摊关房：广播 room_closed，演员标记关闭（WS 循环据此退出）
        assert sockets[owner].last("event.room_closed") is not None
        assert actor.closed is True

        # 落库口径：场次中断（与进程重启一致），房间 CLOSED（大厅列表只列 OPEN）
        assert mysqlCommon.query_mj_game_by_id(gameID)["gameStatus"] == "ABORTED"
        assert mysqlCommon.query_mj_room_by_id(actor.room_id)["roomStatus"] == "CLOSED"
    finally:
        actor._clear_timers()
        # 同一房间是 s5_env 的共享夹具，恢复 OPEN 免得影响后续用例
        mysqlCommon.update_mj_room(mysqlCommon.MJ_ROOM_TABLE, actor.room_id, {"roomStatus": "OPEN"})


async def test_non_host_cannot_end_game(s5_env):
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    guest = s5_env["members"][1]
    try:
        for loginID in s5_env["members"]:
            await actor.handle(loginID, {"type": "seat.ready", "data": {}})
        await actor.handle(owner, {"type": "game.start", "data": {}})
        await actor.handle(guest, {"type": "game.finish", "data": {}})
        error = sockets[guest].last("error")
        assert error is not None
        assert error["data"]["code"] == "NOT_HOST"
        assert actor.engine is not None
        assert actor.status == "playing"
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


# ---------------------------------------------------------------- B-1 收尾（唯一出口）
async def _open_table(actor, s5_env) -> None:
    """四人准备 + 房主开局（收尾类用例共用的起手式）。"""
    for loginID in s5_env["members"]:
        await actor.handle(loginID, {"type": "seat.ready", "data": {}})
    await actor.handle(s5_env["owner"], {"type": "game.start", "data": {}})


def _force_last_round(actor, monkeypatch) -> None:
    """摆成「最后一局刚结算、本场最后一圈已打满」：收尾口径与牌力无关，不必真打满。"""
    actor.engine.phase = "settled"
    monkeypatch.setattr(actor, "_next_dealer_state", lambda: (0, 3, actor.circle_no, True))


def _restore_open(actor) -> None:
    actor._clear_timers()
    if actor._close_task is not None:
        actor._close_task.cancel()
        actor._close_task = None
    mysqlCommon.update_mj_room(mysqlCommon.MJ_ROOM_TABLE, actor.room_id, {"roomStatus": "OPEN"})


async def test_natural_finish_closes_room_and_leaves_lobby(s5_env, monkeypatch):
    """打满一圈（自然结束）→ 场次 FINISHED、房间 CLOSED，大厅列表不再有这桌。"""
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        await _open_table(actor, s5_env)
        gameID = actor.game_id
        assert gameID
        _force_last_round(actor, monkeypatch)

        await actor.handle(owner, {"type": "game.next", "data": {}})

        finished = sockets[owner].last("event.game_finished")
        assert finished is not None
        assert finished["data"]["final"] is True
        assert len(finished["data"]["scores"]) == 4

        # 1) 落库：场次收口、房间 CLOSED（closedYMDHMS 非空）
        assert mysqlCommon.query_mj_game_by_id(gameID)["gameStatus"] == "FINISHED"
        room = mysqlCommon.query_mj_room_by_id(actor.room_id)
        assert room["roomStatus"] == "CLOSED"
        assert room["closedYMDHMS"]

        # 2) 大厅列表只列 OPEN：这桌立刻消失
        listed = mysqlCommon.query_mj_room_list(s5_env["family_id"])
        assert all(int(row["recID"]) != actor.room_id for row in listed)

        # 3) 不立刻广播 room_closed：牌桌先看完最终结算，等最后一个人断线/60s 兜底
        assert sockets[owner].last("event.room_closed") is None
        assert actor.closed is False
        assert actor.status == "finished"
        assert actor.should_reap() is False  # 还有连接在
        assert actor._close_task is not None
    finally:
        _restore_open(actor)


async def test_game_finish_after_natural_finish_is_idempotent(s5_env, monkeypatch):
    """打满后再点"关闭牌桌"：幂等成功（无 NOT_PLAYING），库中仍是一条 CLOSED。"""
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        await _open_table(actor, s5_env)
        _force_last_round(actor, monkeypatch)
        await actor.handle(owner, {"type": "game.next", "data": {}})

        await actor.handle(owner, {"type": "game.finish", "data": {}})

        # 收摊：广播 room_closed，演员标记关闭（WS 循环据此退出）
        assert sockets[owner].last("event.room_closed") is not None
        assert actor.closed is True
        assert actor.status == "closed"
        assert actor.finalized is True
        codes = [message["data"]["code"] for message in sockets[owner].messages if message["type"] == "error"]
        assert "NOT_PLAYING" not in codes
        assert "CLOSE_FAILED" not in codes

        # 重复点击：仍然幂等（不报错、库中仍是一条 CLOSED）
        await actor.handle(owner, {"type": "game.finish", "data": {}})
        codes = [message["data"]["code"] for message in sockets[owner].messages if message["type"] == "error"]
        assert codes == []
        room = mysqlCommon.query_mj_room_by_id(actor.room_id)
        assert room["roomStatus"] == "CLOSED"
        assert int(room["recID"]) == actor.room_id
    finally:
        _restore_open(actor)


async def test_settled_round_does_not_false_alarm_on_write(s5_env):
    """结算落库成功时不得给房主假报「这局数据没存上」。

    口径：`persist.save_round` 成功返回新局 recID；`_on_settled` 只在拿到 None
    （线程池里抛异常）时才发 `error{DB_WRITE_FAILED}`。回归 I6 手测发现的假告警。
    """
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        await _open_table(actor, s5_env)
        engine = actor.engine
        engine.kong_happened = True  # 有杠荒庄：与胡牌局走同一条落库路径
        engine._settle_draw()
        assert engine.result is not None
        await actor._on_settled()

        codes = [
            message["data"]["code"]
            for message in sockets[owner].messages
            if message["type"] == "error"
        ]
        assert "DB_WRITE_FAILED" not in codes
        rounds = mysqlCommon.queryTableGeneral(
            mysqlCommon.MJ_GAME_ROUND_TABLE,
            condList=[["gameID", "=", actor.game_id]],
            columns="recID",
            limitNum=5,
        )
        assert len(rounds) == 1
    finally:
        actor._clear_timers()


async def test_close_room_failure_reports_close_failed_and_can_retry(s5_env, monkeypatch):
    """`close_room` 落库失败：回 CLOSE_FAILED，内存不关、库里仍 OPEN，重试成功。"""
    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]

    def _boom(*args, **kwargs):
        raise persist.PersistError("DB_WRITE_FAILED", "数据保存失败（关闭房间），请重试", 500)

    try:
        await _open_table(actor, s5_env)
        gameID = actor.game_id
        monkeypatch.setattr(persist, "close_room", _boom)

        await actor.handle(owner, {"type": "game.finish", "data": {}})

        error = sockets[owner].last("error")
        assert error is not None
        assert error["data"]["code"] == "CLOSE_FAILED"
        # 不跳转、不收摊：内存房态还在，库里仍 OPEN（不留幽灵房）
        assert actor.closed is False
        assert actor.should_reap() is False
        assert mysqlCommon.query_mj_room_by_id(actor.room_id)["roomStatus"] == "OPEN"

        # 落库恢复后重试：同一个入口成功关房
        monkeypatch.undo()
        await actor.handle(owner, {"type": "game.finish", "data": {}})
        assert actor.closed is True
        assert sockets[owner].last("event.room_closed") is not None
        assert mysqlCommon.query_mj_game_by_id(gameID)["gameStatus"] == "ABORTED"
        assert mysqlCommon.query_mj_room_by_id(actor.room_id)["roomStatus"] == "CLOSED"
    finally:
        _restore_open(actor)
