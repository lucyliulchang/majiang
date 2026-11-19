"""v1.2.0 围观点名（纯内存用例，不依赖测试库，可在任何机器直接跑）。

覆盖：
  - 每座只点前两位（按绑定先后），第三位起不下行；
  - 快照与事件同源：`seats[].spectator_names` 只有前两位，`spectator_count` 仍是真实人数；
  - 昵称缺失回退手机号掩码（不把整号发给全房）；
  - `SPECTATE_REVEAL_NAMES=false` 时整体不下发，人数不受影响。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.localSettings import settings  # noqa: E402
from game.families.generic.config import RuleConfig  # noqa: E402
from realtime.room import RoomActor, SpectateBinding  # noqa: E402
from realtime.snapshot import build_snapshot  # noqa: E402

SEAT0 = "13900000000"
GUESTS = ["13700000001", "13700000002", "13700000003"]


def make_actor() -> RoomActor:
    config = RuleConfig()
    return RoomActor(
        code="123456",
        room_id=1,
        family_id=1,
        family_code="fam_test",
        family_name="测试家庭",
        name="测试房",
        host_login_id=SEAT0,
        rule=config,
        rule_name="家庭标准",
        rule_snapshot={
            "rule_family_code": "generic",
            "template_id": 1,
            "config": config.model_dump(),
        },
    )


def seat0_with_three_viewers(actor: RoomActor) -> None:
    actor.assign(SEAT0, "玩家0", "#C9A063")
    for index, loginID in enumerate(GUESTS):
        actor._roles[loginID] = ("MEMBER", f"围观{index + 1}")
        actor.spectators[loginID] = SpectateBinding(
            target_login_id=SEAT0, display_name=f"围观{index + 1}"
        )


def test_names_only_first_two_in_binding_order():
    actor = make_actor()
    seat0_with_three_viewers(actor)

    names = actor.spectator_names()
    assert names[0] == ["围观1", "围观2"], "第三位起不下行"
    assert names[1:] == [[], [], []]
    assert actor.spectator_counts() == [3, 0, 0, 0], "人数不受点名上限影响"


def test_snapshot_carries_names():
    actor = make_actor()
    seat0_with_three_viewers(actor)

    data = build_snapshot(actor, viewer_seat=0, viewer_login_id=SEAT0)
    seat = data["seats"][0]
    assert seat["spectator_names"] == ["围观1", "围观2"]
    assert seat["spectator_count"] == 3
    assert data["room"]["spectate_seat_viewer_counts"] == [3, 0, 0, 0]


def test_missing_nickname_falls_back_to_masked_login():
    actor = make_actor()
    actor.assign(SEAT0, "玩家0", "#C9A063")
    actor.spectators["13503774661"] = SpectateBinding(target_login_id=SEAT0)

    assert actor.spectator_names()[0] == ["135****4661"]


def test_reveal_switch_off_hides_all_names(monkeypatch):
    actor = make_actor()
    seat0_with_three_viewers(actor)
    monkeypatch.setattr(settings, "spectate_reveal_names", False)

    assert actor.spectator_names() == [[], [], [], []]
    data = build_snapshot(actor, viewer_seat=0, viewer_login_id=SEAT0)
    assert data["seats"][0]["spectator_names"] == []
    assert data["seats"][0]["spectator_count"] == 3
