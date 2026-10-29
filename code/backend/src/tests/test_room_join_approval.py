"""S10：非本家庭成员凭码进桌要房主确认（纯内存演员，不依赖测试库）。

覆盖：
  1. 本家庭成员（含房主）不需要审批，外家庭成员需要；
  2. 外家庭成员连接先挂起：不占座位、不进推送列表，房主快照里能看到申请；
  3. 只有房主能批准/拒绝；批准后补 welcome + 分配座位，拒绝则通知访客；
  4. 待确认的访客断开后，申请随连接一起撤掉。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.families.generic.config import RuleConfig  # noqa: E402
from realtime import persist  # noqa: E402
from realtime.room import RoomActor  # noqa: E402
from realtime.snapshot import build_snapshot  # noqa: E402

HOST = "13800000001"
MEMBER = "13800000002"
VISITOR = "13800000099"


class FakeWS:
    """记录服务端下发的消息，够断言即可。"""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.closed: int | None = None

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)

    async def close(self, code: int = 1000) -> None:
        self.closed = code

    def last(self, msg_type: str) -> dict | None:
        for message in reversed(self.messages):
            if message["type"] == msg_type:
                return message
        return None


def build_actor() -> RoomActor:
    config = RuleConfig()
    return RoomActor(
        code="428915",
        room_id=1,
        family_id=7,
        family_code="lianjia",
        family_name="廉家",
        name="周末家庭局",
        host_login_id=HOST,
        rule=config,
        rule_name="家庭标准",
        rule_snapshot={
            "rule_family_code": "generic",
            "template_id": 1,
            "config": config.model_dump(),
        },
    )


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    """批准后要补 welcome + 系统播报，把落库换成内存实现。"""
    monkeypatch.setattr(persist, "load_messages", lambda roomID, limit=50: [])
    monkeypatch.setattr(
        persist,
        "save_message",
        lambda roomID, familyID, loginID, kind, content: {
            "id": 1,
            "room_id": roomID,
            "login_id": None,
            "kind": "system",
            "content": content,
            "created_at": "2026-01-01T00:00:00",
            "user_name": "系统",
        },
    )


def test_member_and_host_need_no_approval():
    actor = build_actor()
    assert actor.needs_approval(HOST, is_member=True) is False
    assert actor.needs_approval(MEMBER, is_member=True) is False
    assert actor.needs_approval(VISITOR, is_member=False) is True


async def test_visitor_held_until_host_approves():
    actor = build_actor()
    host_ws, visitor_ws = FakeWS(), FakeWS()
    actor.attach(HOST, host_ws)

    actor.add_pending(VISITOR, "亲家公", "#C9A063", visitor_ws)
    assert actor.pending_requests()[0]["login_id"] == VISITOR
    assert VISITOR not in actor.conns  # 批准前不进推送列表，也拿不到房态
    assert actor.slot_of_login(VISITOR) is None

    # 申请只对房主可见
    assert build_snapshot(actor, None, HOST)["join_requests"][0]["login_id"] == VISITOR
    assert build_snapshot(actor, None, MEMBER)["join_requests"] == []

    await actor.approve_join(HOST, VISITOR, True)

    assert VISITOR in actor.approved
    assert actor.pending_requests() == []
    assert VISITOR in actor.conns
    assert actor.slot_of_login(VISITOR) is not None
    assert visitor_ws.last("room.welcome") is not None


async def test_only_host_can_approve():
    actor = build_actor()
    member_ws, visitor_ws = FakeWS(), FakeWS()
    actor.attach(MEMBER, member_ws)
    actor.add_pending(VISITOR, "亲家公", "#C9A063", visitor_ws)

    await actor.approve_join(MEMBER, VISITOR, True)

    assert actor.slot_of_login(VISITOR) is None
    assert actor.pending_requests() != []
    error = member_ws.last("error")
    assert error is not None and error["data"]["code"] == "FORBIDDEN"


async def test_host_rejects_visitor():
    actor = build_actor()
    host_ws, visitor_ws = FakeWS(), FakeWS()
    actor.attach(HOST, host_ws)
    actor.add_pending(VISITOR, "亲家公", "#C9A063", visitor_ws)

    await actor.approve_join(HOST, VISITOR, False)

    assert visitor_ws.last("room.join_denied") is not None
    assert actor.pending_requests() == []
    assert actor.slot_of_login(VISITOR) is None
    # 拒绝只作废本次申请：重进会重新提交，房主误点还能改
    assert actor.needs_approval(VISITOR, is_member=False) is True


async def test_visitor_detach_drops_request():
    actor = build_actor()
    visitor_ws = FakeWS()
    actor.add_pending(VISITOR, "亲家公", "#C9A063", visitor_ws)

    actor.detach(VISITOR, visitor_ws)

    assert actor.pending_requests() == []
