"""WS 层：两段式询问（胡牌优先 / 过胡，改进文档 U-1）。

本模块直接驱动 `RoomActor` 的报文入口（`actor.handle`），断言"客户端看到什么"：
快照 `legal.actions` 的收敛、过胡后同一窗口的补发、越级提交的 `BAD_ACTION`、超时收窗。

刻意不依赖测试库：`room._persist` 对非收尾类写入只记日志（01 §7.4），
落库失败不影响这些断言，因此本用例在任何环境下都能跑（`mahjong_test` 不在时也不跳）。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.families.generic.config import RuleConfig, TurnTimeout  # noqa: E402
from game.tiles import counts_from_tiles  # noqa: E402
from realtime.room import RoomActor  # noqa: E402

MEMBERS = ("13900000001", "13900000002", "13900000003", "13900000004")

# 座位 1：五万既能胡（555m + 三面子 + 99p 将）又能碰（手里两张五万）
HU_PONG_HANDS = {
    0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s",
    1: "55m123m789m123p99p",
    2: "1p2p3p4p5p6p7p8p9p1s2s3s4s",
    3: "1p2p3p4p5p6p7p8p9p1s2s3s4s",
}


# 座位 1 只能吃、座位 2 只能胡：用来验证"胡即收口"不必等吃家表态
CHOW_HU_HANDS = {
    0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s",
    1: "46m1p2p3p4p5p6p7p8p9p1s2s",
    2: "34m123m789m123p11p",
    3: "1p2p3p4p5p6p7p8p9p1s2s3s4s",
}


class FakeWS:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)

    def last(self, msg_type: str) -> dict | None:
        for message in reversed(self.messages):
            if message["type"] == msg_type:
                return message
        return None


def build_actor() -> tuple[RoomActor, dict[str, FakeWS]]:
    rule = RuleConfig(turn_timeout=TurnTimeout(enabled=False))
    actor = RoomActor(
        code="428915",
        room_id=1,
        family_id=1,
        family_code="claimstage",
        family_name="两段式询问",
        name="过胡测试房",
        host_login_id=MEMBERS[0],
        rule=rule,
        rule_name="家庭标准",
        rule_snapshot={"rule_family_code": "generic", "template_id": 0, "config": rule.model_dump()},
    )
    sockets: dict[str, FakeWS] = {}
    for login_id in MEMBERS:
        ws = FakeWS()
        sockets[login_id] = ws
        actor.attach(login_id, ws)
        actor.assign(login_id, f"玩家{login_id[-1]}", "#C9A063")
    return actor, sockets


async def open_table(actor: RoomActor, hand, mapping: dict[int, str]) -> tuple[str, str]:
    """四人准备 + 开桌，然后把牌面摆成"座位 0 打出五万，座位 1 可胡可碰"。"""
    for login_id in MEMBERS:
        await actor.handle(login_id, {"type": "seat.ready", "data": {}})
    await actor.handle(MEMBERS[0], {"type": "game.start", "data": {}})

    engine = actor.engine
    assert engine is not None
    for seat in range(4):
        engine.seats[seat].counts = counts_from_tiles(hand(mapping.get(seat, "")))
        engine.seats[seat].melds = []
        engine.seats[seat].discards = []
    engine.turn = 0
    engine.phase = "discard"
    engine.claim = None
    engine.last_draw = None
    # 抽座后座位编号即物理座位，座位 0 = 庄家/东位
    return actor.slots[0].login_id, actor.slots[1].login_id


def legal_actions(sockets: dict[str, FakeWS], login_id: str) -> list[dict]:
    snapshot = sockets[login_id].last("state.snapshot")
    assert snapshot is not None
    return snapshot["data"]["legal"]["actions"]


def actions(sockets: dict[str, FakeWS], login_id: str) -> list[str]:
    return [item["action"] for item in legal_actions(sockets, login_id)]


async def test_ws_claim_hu_stage_then_reveal_pong(hand):
    """可胡可碰：先只问胡；点"不胡"后同一窗口补出碰，碰照常成立。"""
    actor, sockets = build_actor()
    try:
        discarder, target = await open_table(actor, hand, HU_PONG_HANDS)
        await actor.handle(
            discarder, {"type": "game.action", "data": {"action": "discard", "tiles": [4]}}
        )

        # 第一段：只有 hu/pass（碰被服务端藏起来，前端无需特判）
        assert actions(sockets, target) == ["hu", "pass"]
        claim = sockets[target].last("state.snapshot")["data"]["legal"]
        assert claim["claim_tile"] == 4 and claim["reason"] == "discard"

        await actor.handle(target, {"type": "game.action", "data": {"action": "pass"}})

        # 第二段：同一张牌、同一窗口，补出碰（不含 hu），且能看到倒计时仍属询问阶段
        snapshot = sockets[target].last("state.snapshot")["data"]
        assert [item["action"] for item in snapshot["legal"]["actions"]] == ["pong", "pass"]
        assert snapshot["phase"] == "claim"
        assert snapshot["legal"]["claim_tile"] == 4

        await actor.handle(target, {"type": "game.action", "data": {"action": "pong"}})
        claimed = sockets[target].last("event.claimed")
        assert claimed is not None and claimed["data"]["action"] == "pong"
        snapshot = sockets[target].last("state.snapshot")["data"]
        assert snapshot["phase"] == "discard" and snapshot["turn"] == 1
    finally:
        actor._clear_timers()


async def test_ws_claim_hu_stage_rejects_pong_then_timeout_closes(hand):
    """胡阶段越级提交碰 → BAD_ACTION（不静默吃掉胡）；过胡后不操作 → 超时收窗不卡死。"""
    actor, sockets = build_actor()
    try:
        discarder, target = await open_table(actor, hand, HU_PONG_HANDS)
        await actor.handle(
            discarder, {"type": "game.action", "data": {"action": "discard", "tiles": [4]}}
        )

        await actor.handle(target, {"type": "game.action", "data": {"action": "pong"}})
        error = sockets[target].last("error")
        assert error is not None and error["data"]["code"] == "BAD_ACTION"
        assert actions(sockets, target) == ["hu", "pass"], "被拒后胡还在"

        # 过胡 → 补发碰/过；此时不再操作，等窗口超时
        await actor.handle(target, {"type": "game.action", "data": {"action": "pass"}})
        assert actions(sockets, target) == ["pong", "pass"]

        events = actor.engine.timeout_claim()
        assert events, "超时必须推进牌局"
        await actor._after(events)

        snapshot = sockets[target].last("state.snapshot")["data"]
        assert snapshot["phase"] == "discard" and snapshot["turn"] == 1
        assert snapshot["legal"].get("claim_tile") is None
        assert actor.engine.claim is None
    finally:
        actor._clear_timers()


async def test_ws_hu_settles_without_waiting_for_chow(hand):
    """吃家还没表态，胡家一点就收口：全桌立即看到 event.settled，吃家不必再点。"""
    actor, sockets = build_actor()
    try:
        discarder, chower = await open_table(actor, hand, CHOW_HU_HANDS)
        huer = actor.slots[2].login_id
        await actor.handle(
            discarder, {"type": "game.action", "data": {"action": "discard", "tiles": [4]}}
        )
        assert actions(sockets, chower) == ["chow", "pass"]
        assert actions(sockets, huer) == ["hu", "pass"]

        await actor.handle(huer, {"type": "game.action", "data": {"action": "hu"}})

        settled = sockets[huer].last("event.settled")
        assert settled is not None and settled["data"]["winner_seat"] == 2
        # 吃家一句话没说，牌局已经收口：它的动作条消失、快照进入 settled
        assert actions(sockets, chower) == []
        assert sockets[chower].last("state.snapshot")["data"]["phase"] == "settled"
        assert actor.engine.claim is None
    finally:
        actor._clear_timers()


async def test_ws_claim_safety_timeout_closes_stuck_window(hand, monkeypatch):
    """不限时（默认）也挂一条防卡死长兜底：整窗没人点，到点按过收窗、牌局继续。"""
    from realtime import room as room_module

    monkeypatch.setattr(room_module, "CLAIM_SAFETY_SECONDS", 0.05)
    actor, sockets = build_actor()
    try:
        discarder, target = await open_table(actor, hand, HU_PONG_HANDS)
        await actor.handle(
            discarder, {"type": "game.action", "data": {"action": "discard", "tiles": [4]}}
        )
        snapshot = sockets[target].last("state.snapshot")["data"]
        assert snapshot["phase"] == "claim"
        # 不限时：牌桌上不该出现倒计时压力
        assert snapshot["claim_deadline"] is None
        assert actor._claim_task is not None, "不限时也必须挂防卡死兜底"
        assert actions(sockets, target) == ["hu", "pass"]

        await asyncio.sleep(0.2)  # 等兜底到点

        assert actor.engine.claim is None
        snapshot = sockets[target].last("state.snapshot")["data"]
        assert snapshot["phase"] == "discard" and snapshot["turn"] == 1
        timeout = sockets[target].last("event.claim_timeout")
        assert timeout is not None
        assert "长时间无人响应" in timeout["data"]["message"]
    finally:
        actor._clear_timers()


# 座位 1 手牌 234556 万：吃 4 万时被吃牌可作低/中/高张 → 234 / 345 / 456
CHOW_THREE_HANDS = {
    0: "4m1p2p3p4p5p6p7p8p9p1s2s3s4s",
    1: "234556m1p2p3p4p5p6p",
    2: "1p2p3p4p5p6p7p8p9p1s2s3s",
    3: "1p2p3p4p5p6p7p8p9p1s2s3s",
}


async def test_ws_chow_offers_three_candidates_and_accepts_client_pair(hand):
    """候选从 1 组变 3 组（04 §9.5）；客户端指定的两张只要成顺就能成副露。"""
    actor, sockets = build_actor()
    try:
        discarder, chower = await open_table(actor, hand, CHOW_THREE_HANDS)
        await actor.handle(
            discarder, {"type": "game.action", "data": {"action": "discard", "tiles": [3]}}
        )

        options = legal_actions(sockets, chower)
        chows = [item["tiles"] for item in options if item["action"] == "chow"]
        assert chows == [[1, 2], [2, 4], [4, 5]], "234 / 345 / 456 三组都必须下发"

        # 不走候选里的第一组，改选 456（5万6万）也照样成立
        await actor.handle(
            chower, {"type": "game.action", "data": {"action": "chow", "tiles": [4, 5]}}
        )
        claimed = sockets[chower].last("event.claimed")
        assert claimed is not None and claimed["data"]["tiles"] == [3, 4, 5]
        snapshot = sockets[chower].last("state.snapshot")["data"]
        assert snapshot["phase"] == "discard" and snapshot["turn"] == 1
        melds = snapshot["seats"][1]["melds"]
        assert melds and melds[0]["kind"] == "chow" and melds[0]["tiles"] == [3, 4, 5]
    finally:
        actor._clear_timers()


async def test_ws_chow_rejects_illegal_pair_without_closing_window(hand):
    """构造报文直达后端（2万+6万）→ BAD_CHOW；窗口不关、手牌不动，可改选后正常吃。"""
    actor, sockets = build_actor()
    try:
        discarder, chower = await open_table(actor, hand, CHOW_THREE_HANDS)
        await actor.handle(
            discarder, {"type": "game.action", "data": {"action": "discard", "tiles": [3]}}
        )
        before = list(actor.engine.seats[1].counts)

        await actor.handle(
            chower, {"type": "game.action", "data": {"action": "chow", "tiles": [1, 5]}}
        )
        error = sockets[chower].last("error")
        assert error is not None and error["data"]["code"] == "BAD_CHOW"
        assert actor.engine.claim is not None and actor.engine.claim.responses == {}
        assert actor.engine.seats[1].counts == before
        assert [item["action"] for item in legal_actions(sockets, chower)] == ["chow", "chow", "chow", "pass"]

        await actor.handle(
            chower, {"type": "game.action", "data": {"action": "chow", "tiles": [1, 2]}}
        )
        claimed = sockets[chower].last("event.claimed")
        assert claimed is not None and claimed["data"]["tiles"] == [1, 2, 3]
    finally:
        actor._clear_timers()
