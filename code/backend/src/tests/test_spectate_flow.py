"""S5b 观战跟随与围观上限（04 §9、05 §4.5）。

覆盖验收：
  - 未选目标：hand=[]、spectate=null、legal=[]；
  - 选目标后只有目标手牌明文，其余座位只有 hand_count；
  - 切换目标：旧目标 -1、新目标 +1、全房总数守恒；
  - 第 11 人 SPECTATE_TARGET_FULL 且原绑定不变；
  - 同一 loginID 多标签页只占 1 个名额；
  - 断线 60 秒保留 → 到期释放（用 0 秒配置直接验证释放分支）；
  - 目标离座 → 观战者收到 event.spectate_changed{target_seat:null} 并回到未选择态；
  - 观战者操作返回 NO_SEAT；4×10 满 → spectate_full / ROOM_SPECTATE_FULL；
  - room_join_check 的 spectate.available 随名额变化。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.localSettings import settings  # noqa: E402
from processor import roomService  # noqa: E402
from realtime.room import RoomActor  # noqa: E402
from schemas.rule import RuleConfig  # noqa: E402

pytestmark = pytest.mark.usefixtures("s5_env")

SPECTATORS = [f"13900000{index:03d}" for index in range(1, 46)]


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

    def snapshot(self) -> dict:
        message = self.last("state.snapshot")
        return message["data"] if message else {}


def build_actor(s5_env):
    room = s5_env["room"]
    config = RuleConfig()
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
        rule_snapshot={
            "rule_family_code": "generic",
            "template_id": s5_env["template_id"],
            "config": config.model_dump(),
        },
    )
    sockets = {}
    for loginID in s5_env["members"]:
        ws = FakeWS()
        sockets[loginID] = ws
        actor.attach(loginID, ws)
        actor.assign(loginID, f"玩家{loginID[-1]}", "#C9A063")
    return actor, sockets


def add_spectator(actor, loginID: str) -> FakeWS:
    ws = FakeWS()
    actor.attach(loginID, ws)
    return ws


async def start_game(actor, sockets) -> None:
    for loginID in list(sockets):
        await actor.handle(loginID, {"type": "seat.ready", "data": {}})
    await actor.handle(actor.host_login_id, {"type": "game.start", "data": {}})


async def test_spectator_without_target_gets_no_hand(s5_env):
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    ws = add_spectator(actor, guest)
    try:
        await start_game(actor, sockets)
        await actor.handle(guest, {"type": "state.resync", "data": {}})
        data = ws.snapshot()
        assert data["self_seat"] is None
        assert data["spectate"] is None
        assert data["hand"] == []
        assert data["drawn"] is None
        assert data["legal"]["actions"] == []
        # 公共状态仍然可读
        assert data["phase"] == "discard"
        assert data["wall_count"] > 0
    finally:
        actor._clear_timers()


async def test_select_target_reveals_only_target_hand(s5_env):
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    ws = add_spectator(actor, guest)
    try:
        await start_game(actor, sockets)
        await actor.handle(guest, {"type": "spectate.target", "data": {"seat": 2}})

        data = ws.snapshot()
        assert data["spectate"]["target_seat"] == 2
        assert data["spectate"]["target_login_id"] == s5_env["members"][2]
        assert data["spectate"]["viewer_count"] == 1
        assert data["spectate"]["limit_per_seat"] == settings.spectate_limit_per_seat
        assert data["hand"], "观战目标的手牌应为明文"
        assert data["legal"]["actions"] == [], "观战者不能操作"
        assert data["seats"][2]["spectator_count"] == 1
        assert data["seats"][0]["spectator_count"] == 0

        # 其余座位没有手牌字段，只有张数
        for seat in data["seats"]:
            assert "hand" not in seat
        target = actor.engine.seats[2]
        assert len(data["hand"]) == sum(target.counts)

        event = sockets[s5_env["owner"]].last("event.spectate_changed")
        assert event is not None
        assert event["data"]["target_seat"] == 2
        assert event["data"]["viewer_count"] == 1
        assert event["data"]["seat_viewer_counts"] == [0, 0, 1, 0]
        # 广播里不含观战者身份
        assert "login_id" not in event["data"]
    finally:
        actor._clear_timers()


async def test_switch_target_keeps_total_and_moves_quota(s5_env):
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    add_spectator(actor, guest)
    try:
        await start_game(actor, sockets)
        for seat in (0, 1, 2):
            await actor.handle(guest, {"type": "spectate.target", "data": {"seat": seat}})
            counts = actor.spectator_counts()
            assert counts[seat] == 1
            assert sum(counts) == 1, "切换是名额转移，不是叠加"
        assert actor.spectator_counts() == [0, 0, 1, 0]
    finally:
        actor._clear_timers()


async def test_eleventh_viewer_rejected_and_binding_kept(s5_env):
    actor, sockets = build_actor(s5_env)
    try:
        await start_game(actor, sockets)
        ten = SPECTATORS[:10]
        for loginID in ten:
            add_spectator(actor, loginID)
            await actor.handle(loginID, {"type": "spectate.target", "data": {"seat": 0}})
        assert actor.spectator_counts()[0] == settings.spectate_limit_per_seat

        # 第 11 人先绑 1 号座，再抢满员的 0 号座：拒绝且原绑定不变
        eleventh = SPECTATORS[10]
        ws = add_spectator(actor, eleventh)
        await actor.handle(eleventh, {"type": "spectate.target", "data": {"seat": 1}})
        await actor.handle(eleventh, {"type": "spectate.target", "data": {"seat": 0}})

        error = ws.last("error")
        assert error is not None
        assert error["data"]["code"] == "SPECTATE_TARGET_FULL"
        assert actor.spectators[eleventh].target_login_id == s5_env["members"][1]
        assert actor.spectator_counts() == [10, 1, 0, 0]
    finally:
        actor._clear_timers()


async def test_multi_tab_occupies_single_quota(s5_env):
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    try:
        await start_game(actor, sockets)
        tab1 = FakeWS()
        tab2 = FakeWS()
        actor.attach(guest, tab1)
        actor.attach(guest, tab2)
        await actor.handle(guest, {"type": "spectate.target", "data": {"seat": 3}})
        assert actor.spectator_counts()[3] == 1

        actor.detach(guest, tab1)
        assert guest in actor.spectators, "还有标签页在线，绑定不能释放"

        # 两个标签页都断：进入保留态，名额仍占着
        actor.detach(guest, tab2)
        assert actor.spectator_counts()[3] == 1
        assert guest in actor.spectators
    finally:
        actor._clear_timers()
        for task in list(actor._spectate_tasks.values()):
            task.cancel()


async def test_reserve_expiry_releases_quota(s5_env, monkeypatch):
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    try:
        await start_game(actor, sockets)
        ws = add_spectator(actor, guest)
        await actor.handle(guest, {"type": "spectate.target", "data": {"seat": 2}})
        assert actor.spectator_counts()[2] == 1

        monkeypatch.setattr(settings, "spectate_reserve_seconds", 0)
        actor.detach(guest, ws)
        await actor._spectate_reserve(guest, 0)

        assert guest not in actor.spectators
        assert actor.spectator_counts() == [0, 0, 0, 0]
        event = sockets[s5_env["owner"]].last("event.spectate_changed")
        assert event["data"]["seat_viewer_counts"] == [0, 0, 0, 0]
    finally:
        actor._clear_timers()


async def test_target_leaving_clears_binding(s5_env):
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    ws = add_spectator(actor, guest)
    try:
        await start_game(actor, sockets)
        await actor.handle(guest, {"type": "spectate.target", "data": {"seat": 2}})

        await actor.clear_seat(2)

        assert guest not in actor.spectators
        data = ws.snapshot()
        assert data["spectate"] is None
        assert data["hand"] == []
        event = ws.last("event.spectate_changed")
        assert event["data"]["target_seat"] is None
        assert event["data"]["viewer_count"] == 0
        assert actor.spectator_counts() == [0, 0, 0, 0]
    finally:
        actor._clear_timers()


async def test_binding_follows_login_after_seat_swap(s5_env):
    """抽座换座后仍跟随同一 loginID（按 loginID 绑定，座位只是派生值）。"""
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    ws = add_spectator(actor, guest)
    try:
        await start_game(actor, sockets)
        target_login = s5_env["members"][2]
        await actor.handle(guest, {"type": "spectate.target", "data": {"seat": 2}})
        assert actor.spectators[guest].target_login_id == target_login

        # 模拟抽座：2/3 号座位的玩家互换（座位对象整体交换，engine 状态在真实抽座时随座位重建）
        actor.slots[2], actor.slots[3] = actor.slots[3], actor.slots[2]
        new_seat = actor.seat_of_login(target_login)
        assert new_seat == 3
        await actor.push_all()

        data = ws.snapshot()
        assert data["spectate"]["target_seat"] == 3
        assert actor.spectators[guest].target_login_id == target_login
        assert data["seats"][3]["spectator_count"] == 1
        assert data["seats"][2]["spectator_count"] == 0
    finally:
        actor._clear_timers()


async def test_spectator_cannot_act_but_can_chat(s5_env):
    actor, sockets = build_actor(s5_env)
    guest = SPECTATORS[0]
    ws = add_spectator(actor, guest)
    try:
        await start_game(actor, sockets)
        await actor.handle(guest, {"type": "spectate.target", "data": {"seat": 1}})

        for msg in (
            {"type": "seat.ready", "data": {}},
            {"type": "game.start", "data": {}},
            {"type": "game.action", "data": {"action": "discard", "tiles": [5]}},
        ):
            ws.messages.clear()
            await actor.handle(guest, msg)
            error = ws.last("error")
            assert error is not None and error["data"]["code"] == "NO_SEAT"

        ws.messages.clear()
        await actor.handle(guest, {"type": "chat.send", "data": {"content": "这手牌不错"}})
        chat = ws.last("chat.message")
        assert chat is not None and chat["data"]["login_id"] == guest
    finally:
        actor._clear_timers()


async def test_forty_spots_full_blocks_handshake(s5_env):
    actor, sockets = build_actor(s5_env)
    try:
        await start_game(actor, sockets)
        for index, loginID in enumerate(SPECTATORS[: settings.spectate_room_max]):
            add_spectator(actor, loginID)
            await actor.handle(
                loginID, {"type": "spectate.target", "data": {"seat": index % 4}}
            )
        assert actor.spectate_count() == settings.spectate_room_max
        assert actor.spectate_full() is True
    finally:
        actor._clear_timers()


def test_handshake_returns_4005_when_spots_full(s5_env, monkeypatch):
    """4 座满 + 名额满 → error{ROOM_SPECTATE_FULL} + close(4005)。"""
    from contextlib import ExitStack

    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from common.securityCommon import create_access_token
    from main.app import app
    from processor import accountService
    from realtime.manager import room_manager

    # 观战者也要有 USER_BASIC 档案 + 家庭成员关系，WS 握手才认得出身份
    from common import miscCommon as misc
    from common import mysqlCommon

    now = misc.getTime()
    for loginID in SPECTATORS[:2]:
        accountService.ensureUserBasic(loginID)
        if mysqlCommon.query_mj_family_member(s5_env["family_id"], loginID):
            continue
        mysqlCommon.insert_mj_family_member(
            mysqlCommon.MJ_FAMILY_MEMBER_TABLE,
            {
                "familyMemberKey": f"{s5_env['family_id']}_{loginID}",
                "familyID": s5_env["family_id"],
                "loginID": loginID,
                "memberRole": "MEMBER",
                "memberStatus": "ACTIVE",
                "joinedYMDHMS": now,
                "regID": loginID,
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
    # 把全房名额压到 1，避免真的连 45 条连接
    monkeypatch.setattr(settings, "spectate_room_max", 1)
    code = s5_env["room"]["room_code"]

    def url(loginID: str) -> str:
        return f"/ws?token={create_access_token(loginID, 'member')}&code={code}"

    with TestClient(app) as client, ExitStack() as stack:
        for loginID in s5_env["members"]:
            ws = stack.enter_context(client.websocket_connect(url(loginID)))
            ws.receive_json()  # room.welcome
        viewer = stack.enter_context(client.websocket_connect(url(SPECTATORS[0])))
        viewer.receive_json()  # room.welcome
        viewer.send_json({"type": "spectate.target", "data": {"seat": 0}})

        latecomer = stack.enter_context(client.websocket_connect(url(SPECTATORS[1])))
        error = latecomer.receive_json()
        assert error["type"] == "error"
        assert error["data"]["code"] == "ROOM_SPECTATE_FULL"
        with pytest.raises(WebSocketDisconnect) as closed:
            latecomer.receive_json()
        assert closed.value.code == 4005

    room_manager.remove(code)


def test_join_check_reports_live_viewer_counts(s5_env):
    row = {
        "roomCode": "123456",
        "roomName": "观战房",
        "hostLoginID": "13800000001",
        "templateName": "家庭标准",
        "ruleFamilyCode": "generic",
        "roomStatus": "OPEN",
    }
    full = roomService.joinCheckOut(row, playerCount=4, viewerCounts=[10, 10, 10, 10])
    assert full["spectate"]["viewer_counts"] == [10, 10, 10, 10]
    assert full["spectate"]["available"] is False
    assert full["can_join"] is False

    almost = roomService.joinCheckOut(row, playerCount=4, viewerCounts=[10, 10, 10, 9])
    assert almost["spectate"]["available"] is True
    assert almost["spectate"]["limit_per_seat"] == settings.spectate_limit_per_seat
