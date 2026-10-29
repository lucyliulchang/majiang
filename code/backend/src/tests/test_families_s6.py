"""S6 验收：规则族注册表、发牌、抽座与轮庄、荒庄二分、快照不可变、能力校验。

对照口径：03 §1–§4（含 §3.4 座位/庄家/局风、§3.5 发牌、§3.6 荒庄）、§9–§11。
前 6 组是纯引擎/注册表用例（不触库）；后 4 组走真实测试库 `mahjong_test`（`s5_env`）。
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.bizCommon import BizError  # noqa: E402
from game.engine import dealer_of_round, draw_seats, round_wind_of  # noqa: E402
from game.families import registry  # noqa: E402
from game.families.generic.config import RuleConfig, default_fan_table  # noqa: E402
from game.families.generic.engine import GenericEngine  # noqa: E402
from game.tiles import empty_counts, new_wall  # noqa: E402

SEGMENT = 34


# ---------------------------------------------------------------- 1. 注册表


def test_generic_family_registered_and_ready():
    plugin = registry.get_family("generic")
    assert plugin is not None
    assert plugin.engine_code == "generic"
    assert plugin.ready is True, plugin.issues
    assert plugin.config_model is RuleConfig
    assert plugin.capability["tile_set"] == "136"
    assert plugin.capability["patterns"] == [
        "standard",
        "seven_pairs",
        "thirteen_orphans",
        "thirteen_unrelated",
    ]
    assert [preset.template_code for preset in plugin.presets] == [
        "generic_standard",
        "generic_no_chow",
        "generic_unrelated",
        "generic_casual",
    ]


def test_guangdong_family_registered_and_ready():
    plugin = registry.get_family("guangdong")
    assert plugin is not None and plugin.ready is True
    # 03 §5：capability 去掉 thirteen_unrelated、wind_fan=false
    assert "thirteen_unrelated" not in plugin.capability["patterns"]
    assert plugin.capability["wind_fan"] is False


def test_unregistered_family_not_ready():
    # S7 起 sichuan / baishi 都已接入引擎，未注册族的门禁改用不存在的编码验证
    assert registry.get_family("no_such_family") is None
    ready, issues = registry.is_ready("no_such_family")
    assert ready is False and issues


def test_require_unknown_family_raises():
    with pytest.raises(registry.FamilyError) as error:
        registry.require_family("no_such_family")
    assert error.value.code == "RULE_FAMILY_NOT_FOUND"


def test_capability_missing_field_fails_selfcheck():
    broken = dict(registry.capability_of("generic"))
    broken.pop("settlement")
    ready, issues = registry.is_ready("generic", broken)
    assert ready is False
    assert any("settlement" in issue for issue in issues)


def test_capability_unknown_pattern_fails_selfcheck():
    broken = {**registry.capability_of("generic"), "patterns": ["standard", "no_such_pattern"]}
    ready, issues = registry.is_ready("generic", broken)
    assert ready is False
    assert any("no_such_pattern" in issue for issue in issues)


def test_capability_unknown_tile_set_fails_selfcheck():
    broken = {**registry.capability_of("generic"), "tile_set": "144"}
    ready, issues = registry.is_ready("generic", broken)
    assert ready is False
    assert any("tile_set" in issue for issue in issues)


def test_create_engine_uses_family_plugin():
    engine = registry.create_engine("generic", RuleConfig(), _seats())
    assert isinstance(engine, GenericEngine)
    assert engine.family_code == "generic"
    assert len(engine.tile_set) == 34

    guangdong = registry.create_engine("guangdong", RuleConfig(), _seats())
    assert guangdong.family_code == "guangdong"


def test_engines_satisfy_rule_engine_protocol():
    """注册表里的每个引擎都必须满足 03 §3.2 的 `RuleEngine` 协议。"""
    from game.engine import RuleEngine

    for code in registry.registered_codes():
        engine = registry.create_engine(code, registry.config_model_of(code)(), _seats())
        assert isinstance(engine, RuleEngine), code
        for method in (
            "start_round",
            "legal_actions",
            "apply_action",
            "timeout_claim",
            "tenpai_map",
            "settlement",
            "next_dealer",
            "snapshot_options",
        ):
            assert callable(getattr(engine, method)), f"{code}.{method}"


def _seats():
    from game.engine import SeatState

    return [
        SeatState(seat=index, login_id=f"1380000000{index}", display_name=f"玩家{index}", color="#C9A063")
        for index in range(4)
    ]


# ---------------------------------------------------------------- 2. 发牌


def _expected_sequence(wall: list[int], break_seat: int, stacks: int) -> list[int]:
    """独立复算取牌序列（03 §3.5）：从开牌家牌墙右端数 stacks 墩，其后一墩起。"""
    offset = max(0, 17 - min(stacks, 17)) * 2
    head = wall[break_seat * SEGMENT : (break_seat + 1) * SEGMENT]
    sequence = head[offset:] + head[:offset]
    for step in range(1, 4):
        left = ((break_seat + step) % 4) * SEGMENT
        sequence.extend(wall[left : left + SEGMENT])
    return sequence


def test_deal_counts_and_jump_tiles_are_reproducible(engine_factory):
    seed = 20261027
    engine = engine_factory(rng=random.Random(seed))
    events = engine.start_round()

    # 独立复算：同一 seed 先洗牌、再掷骰
    rng = random.Random(seed)
    wall = new_wall(rng, "136")
    dice = [rng.randint(1, 6), rng.randint(1, 6)]
    total = dice[0] + dice[1]
    break_seat = (engine.dealer_seat + total - 1) % 4
    sequence = _expected_sequence(wall, break_seat, total)
    jump = sequence[48:53]  # 12 轮 × 4 张之后的 5 张

    started = events[0]
    assert started["type"] == "event.round_started"
    deal = started["data"]["deal"]
    assert deal["dice"] == dice
    assert deal["break_seat"] == break_seat
    assert deal["break_stack"] == total

    # 庄家 14、闲家各 13；跳牌第 1、第 5 张归庄家，第 2/3/4 张依次给下家/对家/上家
    assert sum(engine.seats[0].counts) == 14
    assert [sum(engine.seats[seat].counts) for seat in (1, 2, 3)] == [13, 13, 13]
    assert engine.seats[0].counts[jump[0]] >= 1
    assert engine.seats[0].counts[jump[4]] >= 1
    for index, seat in enumerate((1, 2, 3), start=1):
        assert engine.seats[seat].counts[jump[index]] >= 1
    # 首轮庄家不摸牌，直接出牌；drawn 为跳牌第 5 张
    assert engine.last_draw == jump[4]
    assert engine.phase == "discard"
    assert engine.turn == engine.dealer_seat
    assert engine.remaining == 136 - 53


def test_dealer_discards_first_without_drawing(engine_factory):
    engine = engine_factory()
    engine.start_round()
    before = list(engine.seats[0].counts)
    assert sum(before) == 14
    tile = next(index for index, count in enumerate(before) if count > 0)
    handAfter = sum(before) - 1
    engine.apply_action(0, {"action": "discard", "tiles": [tile]})
    if engine.phase == "claim":
        engine.timeout_claim()  # 全部过牌，避免偶然的碰/吃干扰断言
    # 出牌后轮到下家摸牌，庄家手上少一张
    assert sum(engine.seats[0].counts) == handAfter == 13
    assert engine.phase == "discard"
    assert engine.turn == 1


def test_seat_wind_rotates_with_dealer(engine_factory):
    engine = engine_factory(dealer_seat=2)
    engine.start_round()
    assert [engine.seat_wind(seat) for seat in range(4)] == [2, 3, 0, 1]


# ---------------------------------------------------------------- 3. 抽座与轮庄


def test_draw_seats_assigns_four_distinct_logins_with_dealer_east():
    logins = ["13900000001", "13900000002", "13900000003", "13900000004"]
    first = draw_seats(logins, random.Random(9527))
    second = draw_seats(logins, random.Random(9527))
    assert first == second, "同 seed 必须可复现"
    assert first["dealer_seat"] == 0

    assignments = first["assignments"]
    assert [entry["seat"] for entry in assignments] == [0, 1, 2, 3]
    assert {entry["login_id"] for entry in assignments} == set(logins)
    for entry in assignments:
        assert len(entry["dice"]) == 2
        assert all(1 <= value <= 6 for value in entry["dice"])


def test_draw_seats_requires_four_players():
    with pytest.raises(Exception):
        draw_seats(["13900000001"], random.Random(1))


def test_dealer_and_round_wind_follow_round_no():
    assert [dealer_of_round(n) for n in (1, 2, 3, 4)] == [0, 1, 2, 3]
    assert [round_wind_of(n) for n in (1, 2, 3, 4)] == [0, 1, 2, 3]
    # 第 n 局庄家 = 座位 n-1，局风随之东南西北（03 §3.4）
    for roundNo in (1, 2, 3, 4):
        engine = registry.create_engine(
            "generic", RuleConfig(), _seats(), round_no=roundNo
        )
        assert engine.dealer_seat == roundNo - 1
        assert engine.round_wind == roundNo - 1
        # 每局换庄：北位（座位 3）下庄即圈结束
        assert engine.next_dealer() == (engine.dealer_seat + 1) % 4


def test_next_dealer_never_continues():
    engine = registry.create_engine("generic", RuleConfig(), _seats(), round_no=1)
    engine.start_round()
    # 不支持连庄：无论谁胡、荒庄与否，庄家都交给下家（03 §3.4）
    assert engine.next_dealer() == 1
    assert engine.next_dealer(None) == 1


# ---------------------------------------------------------------- 4. 荒庄二分（纯引擎）


def test_restart_keeps_round_no_dealer_and_wind(engine_factory, hand):
    from game.tiles import counts_from_tiles

    engine = engine_factory(round_no=2)
    engine.start_round()
    engine.seats[0].counts = counts_from_tiles(hand("5m1p2p3p4p5p6p7p8p9p1s2s3s4s"))
    for seat in (1, 2, 3):
        engine.seats[seat].counts = empty_counts()
    engine.turn = 0
    engine.phase = "discard"
    engine.front = engine.back + 1

    events = engine.apply_action(0, {"action": "discard", "tiles": [4]})
    assert any(event["type"] == "event.round_restarted" for event in events)
    assert engine.phase == "discard"
    assert engine.result is None
    assert engine.round_no == 2
    assert engine.dealer_seat == 1
    assert engine.round_wind == 1


# ---------------------------------------------------------------- 5. 开关纪律与快照选项


def test_snapshot_options_hide_disabled_values():
    from game.families.generic.config import KongScore, ToggleValue, TurnTimeout

    rule = RuleConfig(
        turn_timeout=TurnTimeout(enabled=False, seconds=99),
        kong_score=KongScore(enabled=False, exposed=9, hidden=9, added=9),
        ting_hint=ToggleValue(enabled=False, value=7),
    )
    engine = registry.create_engine("generic", rule, _seats())
    options = engine.snapshot_options()
    assert options["turn_timeout"] == {"enabled": False}
    assert options["kong_score"] == {"enabled": False}
    assert options["ting_hint"] == {"enabled": False}
    assert options["draw_penalty"] == {"enabled": False}
    for key in ("turn_timeout", "kong_score", "ting_hint", "draw_penalty"):
        assert set(options[key]) == {"enabled"}, f"{key} 关闭时不得下发从属值"


# ---------------------------------------------------------------- 6. 配置模型（不触库）


def test_legacy_dealer_switch_keys_ignored_with_warning(caplog):
    config = RuleConfig.model_validate(
        {"dealer_continue_on_win": False, "dealer_continue_on_draw": False, "base_score": 3}
    )
    dumped = config.model_dump()
    assert "dealer_continue_on_win" not in dumped
    assert "dealer_continue_on_draw" not in dumped
    assert config.base_score == 3
    assert any("dealer_continue_on_win" in record.message for record in caplog.records)


def test_unknown_config_field_rejected_by_model():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RuleConfig.model_validate({"no_such_field": 1})


def test_rounds_per_game_is_fixed_to_four():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RuleConfig(rounds_per_game=8)
    assert RuleConfig().rounds_per_game == 4


def test_default_fan_table_is_twenty_items():
    table = default_fan_table()
    assert len(table) == 20
    assert len({item.id for item in table}) == 20
    assert table[0].id == "ping_hu"


# ---------------------------------------------------------------- 7. 能力校验（DB：族行）


@pytest.mark.usefixtures("s5_env")
def test_validate_rejects_unknown_field_with_400():
    from processor import ruleService

    with pytest.raises(BizError) as error:
        ruleService.validateConfig("generic", {"no_such_field": 1})
    assert error.value.code == "RULE_CONFIG_INVALID"
    assert error.value.httpStatus == 400
    assert "no_such_field" in error.value.message


@pytest.mark.usefixtures("s5_env")
def test_validate_rejects_switch_outside_capability():
    from processor import ruleService

    # 族不支持某开关（例如某族只开放「出牌限时」）：白名单层直接 400
    capability = {**registry.capability_of("generic"), "switches": ["turn_timeout"]}
    config = RuleConfig()
    with pytest.raises(BizError) as error:
        ruleService._assertCapability(capability, config, {"kong_score": {"enabled": True}})
    assert error.value.code == "RULE_SWITCH_UNSUPPORTED"
    assert error.value.httpStatus == 400


@pytest.mark.usefixtures("s5_env")
def test_validate_rejects_capability_forbid_chow():
    from processor import ruleService

    capability = {**registry.capability_of("generic"), "allow_chow": False}
    with pytest.raises(BizError) as error:
        ruleService._assertCapability(capability, RuleConfig(allow_chow=True), {})
    assert error.value.code == "RULE_SWITCH_UNSUPPORTED"


@pytest.mark.usefixtures("s5_env")
def test_validate_rejects_capability_forbid_fan_cap():
    from processor import ruleService

    capability = {**registry.capability_of("generic"), "fan_cap_allowed": False}
    with pytest.raises(BizError) as error:
        ruleService._assertCapability(capability, RuleConfig(fan_cap=8), {})
    assert error.value.code == "RULE_FAN_CAP_UNSUPPORTED"


@pytest.mark.usefixtures("s5_env")
def test_validate_rejects_pattern_outside_capability():
    from processor import ruleService

    config = RuleConfig().model_dump()
    config["patterns"]["thirteen_unrelated"] = {"enabled": True}
    with pytest.raises(BizError) as error:
        ruleService.validateConfig("guangdong", config)  # 广东族无十三不靠
    assert error.value.code == "RULE_SWITCH_UNSUPPORTED"


@pytest.mark.usefixtures("s5_env")
def test_validate_accepts_legacy_keys_and_warns(caplog):
    from processor import ruleService

    config = ruleService.validateConfig(
        "generic", {"dealer_continue_on_win": True, "dealer_continue_on_draw": True}
    )
    assert "dealer_continue_on_win" not in config.model_dump()
    assert any("dealer_continue_on_win" in record.message for record in caplog.records)


# ---------------------------------------------------------------- 8. 快照不可变（DB）


@pytest.mark.usefixtures("s5_env")
def test_room_snapshot_frozen_after_template_edit(s5_env):
    from common import mysqlCommon
    from processor import roomService, ruleService
    from realtime import persist

    owner = s5_env["owner"]
    familyID = s5_env["family_id"]
    familyCode = s5_env["family_code"]

    duplicated = ruleService.duplicateTemplate(
        owner, s5_env["template_id"], familyID, familyCode, "S6 快照模板"
    )
    originalConfig = duplicated["config"].copy()
    room = roomService.createRoom(owner, familyID, familyCode, "S6 快照房", duplicated["id"])
    snapshot = mysqlCommon.query_mj_room_by_id(room["id"])["ruleSnapshot"]
    assert snapshot["rule_family_code"] == "generic"
    assert snapshot["engine_code"] == "generic"
    assert snapshot["capability"]["tile_set"] == "136"
    assert snapshot["config"]["base_score"] == originalConfig["base_score"]
    assert snapshot["captured_ymdhms"]

    # 改模板：开桌快照不受影响
    changed = dict(originalConfig)
    changed["base_score"] = 9
    ruleService.updateTemplate(owner, duplicated["id"], rawConfig=changed)
    assert ruleService.getTemplate(owner, duplicated["id"])["config"]["base_score"] == 9
    assert mysqlCommon.query_mj_room_by_id(room["id"])["ruleSnapshot"]["config"]["base_score"] == originalConfig["base_score"]

    # 开局写入 mj_game 的是同一份开桌快照（03 §11：两者不可变）
    seats = [(index, loginID, f"玩家{index}") for index, loginID in enumerate(s5_env["members"])]
    gameID = persist.open_game(
        room["id"], familyID, "generic", snapshot, seats, {"dealer_seat": 0, "assignments": []}
    )
    game = mysqlCommon.query_mj_game_by_id(gameID)
    assert game["ruleSnapshot"] == snapshot
    assert game["seatDrawJson"]["dealer_seat"] == 0

    mysqlCommon.update_mj_game_status(gameID, "FINISHED")
    mysqlCommon.delete_mj_soft(mysqlCommon.MJ_ROOM_TABLE, room["id"], "pytest")


# ---------------------------------------------------------------- 9. 房间流程（抽座/轮庄/荒庄）


class _FakeWS:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)

    def last(self, msgType: str) -> dict | None:
        for message in reversed(self.messages):
            if message["type"] == msgType:
                return message
        return None

    def count(self, msgType: str) -> int:
        return sum(1 for message in self.messages if message["type"] == msgType)


def _build_actor(s5_env, rule: RuleConfig | None = None):
    """房间演员：4 名家庭成员入座 + 一个 generic 规则快照（真实测试库）。"""
    from realtime.room import RoomActor

    room = s5_env["room"]
    config = rule or RuleConfig()
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
            "engine_code": "generic",
            "template_id": s5_env["template_id"],
            "template_name": "家庭标准",
            "config": config.model_dump(),
            "capability": registry.capability_of("generic"),
            "captured_ymdhms": "20261027120000",
        },
    )
    sockets: dict[str, _FakeWS] = {}
    for loginID in s5_env["members"]:
        ws = _FakeWS()
        sockets[loginID] = ws
        actor.attach(loginID, ws)
        actor.assign(loginID, f"玩家{loginID[-1]}", "#C9A063")
    return actor, sockets


async def _ready_and_start(actor, sockets) -> None:
    for loginID in list(sockets):
        await actor.handle(loginID, {"type": "seat.ready", "data": {}})
    await actor.handle(actor.host_login_id, {"type": "game.start", "data": {}})


@pytest.mark.usefixtures("s5_env")
async def test_game_start_draws_seats_and_broadcasts(s5_env):
    actor, sockets = _build_actor(s5_env)
    try:
        await _ready_and_start(actor, sockets)
        drawn = sockets[s5_env["owner"]].last("event.seats_drawn")
        assert drawn is not None
        data = drawn["data"]
        assert data["dealer_seat"] == 0
        assert data["round_no"] == 1
        assert [entry["seat"] for entry in data["assignments"]] == [0, 1, 2, 3]
        assert {entry["login_id"] for entry in data["assignments"]} == set(s5_env["members"])

        # 座位对象按抽座结果重排：下标 = 座位号
        for seat, slot in enumerate(actor.slots):
            assert slot.seat == seat
        assert actor.engine is not None
        assert actor.engine.turn == 0
        assert actor.engine.dealer_seat == 0
        snapshot = sockets[s5_env["owner"]].last("state.snapshot")["data"]
        assert snapshot["seats"][0]["is_dealer"] is True
        assert [seat["wind"] for seat in snapshot["seats"]] == [0, 1, 2, 3]
        assert snapshot["round_wind"] == 0
    finally:
        actor._clear_timers()


@pytest.mark.usefixtures("s5_env")
async def test_round_two_rotates_dealer_without_redraw(s5_env):
    from common import mysqlCommon

    actor, sockets = _build_actor(s5_env)
    try:
        await _ready_and_start(actor, sockets)
        drawnBefore = len([m for m in sockets[s5_env["owner"]].messages if m["type"] == "event.seats_drawn"])
        assert drawnBefore == 1

        engine = actor.engine
        for seat in engine.seats:
            if seat != engine.turn:
                engine.seats[seat].counts = empty_counts()
        engine.front = engine.back + 1
        engine.kong_happened = True  # 直接进荒庄分支，先把第 1 局结算掉
        tile = next(index for index, count in enumerate(engine.seats[engine.turn].counts) if count > 0)
        await actor.handle(
            actor.slots[engine.turn].login_id,
            {"type": "game.action", "data": {"action": "discard", "tiles": [tile]}},
        )
        assert engine.phase == "settled"

        await actor.handle(actor.host_login_id, {"type": "game.next", "data": {}})
        assert actor.engine.round_no == 2
        assert actor.engine.dealer_seat == 1
        assert actor.engine.round_wind == 1
        # 圈内不重抽：seats_drawn 仍只有 1 次
        drawnAfter = len([m for m in sockets[s5_env["owner"]].messages if m["type"] == "event.seats_drawn"])
        assert drawnAfter == 1

        # 第 2 局落库的 roundWind 与局序一致
        rounds = mysqlCommon.queryTableGeneral(
            mysqlCommon.MJ_GAME_ROUND_TABLE,
            condList=[["gameID", "=", actor.game_id]],
            columns="recID,roundNo,roundWind,winnerSeat",
            order="create",
            limitNum=10,
        )
        assert len(rounds) == 1
        assert int(rounds[0]["roundNo"]) == 1
        assert int(rounds[0]["roundWind"]) == 0
    finally:
        actor._clear_timers()


@pytest.mark.usefixtures("s5_env")
async def test_no_kong_draw_restarts_without_persisting(s5_env):
    from common import mysqlCommon

    actor, sockets = _build_actor(s5_env)
    try:
        await _ready_and_start(actor, sockets)
        engine = actor.engine
        for seat in engine.seats:
            if seat != engine.turn:
                engine.seats[seat].counts = empty_counts()
        engine.front = engine.back + 1
        tile = next(index for index, count in enumerate(engine.seats[engine.turn].counts) if count > 0)
        loginID = actor.slots[engine.turn].login_id
        await actor.handle(
            loginID, {"type": "game.action", "data": {"action": "discard", "tiles": [tile]}}
        )

        assert engine.restarts == 1
        assert engine.phase == "discard"
        assert engine.round_no == 1 and engine.dealer_seat == 0 and engine.round_wind == 0
        assert actor.last_result is None, "重发不落库、不产生结算"
        assert sockets[s5_env["owner"]].last("event.round_restarted") is not None
        rounds = mysqlCommon.queryTableGeneral(
            mysqlCommon.MJ_GAME_ROUND_TABLE,
            condList=[["gameID", "=", actor.game_id]],
            columns="recID",
            order="create",
            limitNum=10,
        )
        assert rounds == []
    finally:
        actor._clear_timers()


@pytest.mark.usefixtures("s5_env")
async def test_kong_draw_settles_and_persists(s5_env):
    from common import mysqlCommon

    actor, sockets = _build_actor(s5_env)
    try:
        await _ready_and_start(actor, sockets)
        engine = actor.engine
        seat = engine.turn
        loginID = actor.slots[seat].login_id
        for other in engine.seats:
            if other != seat:
                engine.seats[other].counts = empty_counts()
        engine.seats[seat].counts = empty_counts()
        engine.seats[seat].counts[0] = 4
        engine.seats[seat].counts[9] = 10

        await actor.handle(
            loginID,
            {"type": "game.action", "data": {"action": "kong", "kong_kind": "hidden", "tiles": [0]}},
        )
        assert engine.kong_happened is True

        engine.front = engine.back + 1
        await actor.handle(
            loginID, {"type": "game.action", "data": {"action": "discard", "tiles": [9]}}
        )
        assert engine.phase == "settled"
        assert actor.last_result["is_draw"] is True
        assert actor.last_result["winner_seat"] is None
        # 杠分保留（暗杠 2 分 × 三家），合计守恒
        assert sum(actor.last_result["score_delta"]) == 0
        assert actor.last_result["score_delta"][seat] > 0

        rounds = mysqlCommon.queryTableGeneral(
            mysqlCommon.MJ_GAME_ROUND_TABLE,
            condList=[["gameID", "=", actor.game_id]],
            columns="recID,roundNo,winnerSeat,winType,scoreDeltaJson",
            order="create",
            limitNum=10,
        )
        assert len(rounds) == 1, "有杠荒庄必须落库"
        assert rounds[0]["winnerSeat"] == ""
        assert rounds[0]["winType"] == "none"
        stored = rounds[0]["scoreDeltaJson"]
        stored = json.loads(stored) if isinstance(stored, str) else stored
        assert sum(int(value) for value in stored) == 0
    finally:
        actor._clear_timers()


@pytest.mark.usefixtures("s5_env")
async def test_four_rounds_close_the_circle(s5_env):
    """北位（座位 3）庄家下庄即圈结束：一圈恰好 4 局，局风东→南→西→北（03 §3.4）。"""
    actor, sockets = _build_actor(s5_env)
    try:
        await _ready_and_start(actor, sockets)
        seen: list[tuple[int, int, int]] = []
        for roundNo in (1, 2, 3, 4):
            engine = actor.engine
            assert engine.round_no == roundNo
            seen.append((engine.round_no, engine.dealer_seat, engine.round_wind))

            # 有杠荒庄快速结算，避免依赖具体牌型
            for seat in engine.seats:
                if seat != engine.turn:
                    engine.seats[seat].counts = empty_counts()
            engine.kong_happened = True
            engine.front = engine.back + 1
            tile = next(
                index
                for index, count in enumerate(engine.seats[engine.turn].counts)
                if count > 0
            )
            await actor.handle(
                actor.slots[engine.turn].login_id,
                {"type": "game.action", "data": {"action": "discard", "tiles": [tile]}},
            )
            assert engine.phase == "settled"
            await actor.handle(actor.host_login_id, {"type": "game.next", "data": {}})

        assert seen == [(1, 0, 0), (2, 1, 1), (3, 2, 2), (4, 3, 3)]
        assert actor.status == "finished"
        assert sockets[s5_env["owner"]].last("event.game_finished") is not None
        # 圈内始终只抽一次座
        assert sockets[s5_env["owner"]].count("event.seats_drawn") == 1
    finally:
        actor._clear_timers()


@pytest.mark.usefixtures("s5_env")
async def test_snapshot_has_no_tenpai_when_ting_hint_disabled(s5_env):
    from game.families.generic.config import ToggleValue

    actor, sockets = _build_actor(s5_env, RuleConfig(ting_hint=ToggleValue(enabled=False)))
    try:
        await _ready_and_start(actor, sockets)
        data = sockets[s5_env["owner"]].last("state.snapshot")["data"]
        assert data["tenpai"] == {}
        assert data["rule_options"]["ting_hint"] == {"enabled": False}
    finally:
        actor._clear_timers()
