"""一场时长（v1.1.0）：默认 4 圈 × 每圈 4 个庄次，开桌时可按桌覆盖圈数。

覆盖三块：
- 规则配置：`circles_per_game` 默认 4、只允许 1/2/4/8，进 brief；
- 纯函数 `nextRoundState`：连庄不动、下庄推进、圈满换圈、打满圈数收场；
- 引擎/开桌：引擎带圈序，开桌覆盖只改本次快照、不动模板。
"""

import pytest

from game.families.generic.config import (
    ALLOWED_CIRCLES_PER_GAME,
    CIRCLES_PER_GAME,
    RuleConfig,
)
from realtime.room import ROUNDS_PER_CIRCLE, nextRoundState


# ---------------- 规则配置 ----------------

def test_default_circles_is_four():
    assert CIRCLES_PER_GAME == 4
    assert ROUNDS_PER_CIRCLE == 4
    config = RuleConfig()
    assert config.circles_per_game == 4
    assert config.brief()["circles_per_game"] == 4
    assert config.brief()["rounds_per_game"] == 4


@pytest.mark.parametrize("circles", ALLOWED_CIRCLES_PER_GAME)
def test_circles_accepts_allowed_values(circles):
    assert RuleConfig(circles_per_game=circles).circles_per_game == circles


@pytest.mark.parametrize("circles", [0, 3, 5, 16, -4])
def test_circles_rejects_other_values(circles):
    with pytest.raises(ValueError, match="圈数"):
        RuleConfig(circles_per_game=circles)


def test_baishi_supports_circles():
    from game.families.baishi.config import RuleConfig as BaishiConfig

    config = BaishiConfig(circles_per_game=8)
    assert config.circles_per_game == 8
    assert config.brief()["circles_per_game"] == 8
    with pytest.raises(ValueError, match="圈数"):
        BaishiConfig(circles_per_game=3)


# ---------------- 圈序推进（纯函数） ----------------

def test_dealer_continue_keeps_wind_and_circle():
    # 庄家胡牌连庄：庄位、局风、圈序都不动
    assert nextRoundState(0, 0, 1, 0, 4, 4) == (0, 0, 1, False)


def test_wind_advances_within_circle():
    assert nextRoundState(0, 0, 1, 1, 4, 4) == (1, 1, 1, False)
    assert nextRoundState(1, 1, 1, 2, 4, 4) == (2, 2, 1, False)
    assert nextRoundState(2, 2, 1, 3, 4, 4) == (3, 3, 1, False)


def test_circle_advances_after_north_dealer():
    # 北位下庄 → 本圈结束：圈序 +1、局风回到东风、庄家回到东位
    assert nextRoundState(3, 3, 1, 0, 4, 4) == (0, 0, 2, False)
    assert nextRoundState(3, 3, 3, 0, 4, 4) == (0, 0, 4, False)


def test_game_finishes_on_last_circle():
    assert nextRoundState(3, 3, 4, 0, 4, 4) == (0, 0, 4, True)
    assert nextRoundState(3, 3, 1, 0, 4, 1) == (0, 0, 1, True)


def test_single_circle_game_ends_after_four_dealers():
    # 兼容老口径：1 圈的房打完 4 个庄次即收场
    wind = 0
    circle = 1
    dealer = 0
    rounds = 0
    while True:
        rounds += 1
        dealer, wind, circle, finished = nextRoundState(dealer, wind, circle, (dealer + 1) % 4, 4, 1)
        if finished:
            break
    assert rounds == 4
    assert circle == 1


def test_four_circle_game_is_sixteen_dealer_turns_without_continue():
    wind = 0
    circle = 1
    dealer = 0
    rounds = 0
    while True:
        rounds += 1
        dealer, wind, circle, finished = nextRoundState(dealer, wind, circle, (dealer + 1) % 4, 4, 4)
        if finished:
            break
    assert (rounds, circle) == (16, 4)


def test_default_total_circles_is_four_without_config_field():
    """老规则对象没有 `circles_per_game` 时按 4 圈，不能打成 1 圈就收场。"""
    assert nextRoundState(3, 3, 1, 0) == (0, 0, 2, False)
    assert nextRoundState(3, 3, 4, 0) == (0, 0, 4, True)


def test_snapshot_options_fall_back_to_four_circles():
    from types import SimpleNamespace

    from processor.ruleService import _snapshotOptions

    legacy = SimpleNamespace(rounds_per_game=4, claim_window_seconds=8, allow_chow=True)
    assert _snapshotOptions(legacy)["circles_per_game"] == CIRCLES_PER_GAME == 4


# ---------------- 引擎与快照 ----------------

def test_engine_carries_circle_no(engine_factory):
    engine = engine_factory(round_no=5, dealer_seat=0, circle_no=2)
    assert engine.circle_no == 2
    options = engine.snapshot_options()
    assert options["circle_no"] == 2
    assert options["rounds_per_circle"] == 4
    assert options["circles_per_game"] == 4


def test_engine_round_started_event_has_circle_no(engine_factory):
    engine = engine_factory(round_no=1, circle_no=1)
    events = engine.start_round()
    started = [item for item in events if item["type"] == "event.round_started"]
    assert started and started[0]["data"]["circle_no"] == 1


# ---------------- 开桌覆盖圈数（真实库） ----------------

def test_create_room_overrides_circles_in_snapshot(mysql_ready, s5_env):
    import json

    from common import mysqlCommon
    from processor import roomService

    room = roomService.createRoom(
        s5_env["owner"],
        s5_env["family_id"],
        s5_env["family_code"],
        "圈数覆盖测试",
        s5_env["template_id"],
        circles=2,
    )
    try:
        snapshot = roomService._loadRoom(room["id"])["ruleSnapshot"]
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        assert snapshot["config"]["circles_per_game"] == 2
        assert snapshot["options"]["circles_per_game"] == 2
        # 每圈局数固定 4，不受圈数覆盖影响
        assert snapshot["config"]["rounds_per_game"] == 4
    finally:
        mysqlCommon.update_mj_room_close(room["id"], "pytest")


def test_create_room_rejects_illegal_circles(mysql_ready, s5_env):
    from processor import roomService
    from processor.roomService import RoomServiceError

    with pytest.raises(RoomServiceError) as info:
        roomService.createRoom(
            s5_env["owner"],
            s5_env["family_id"],
            s5_env["family_code"],
            "非法圈数",
            s5_env["template_id"],
            circles=3,
        )
    assert info.value.code == "RULE_CIRCLES_INVALID"
