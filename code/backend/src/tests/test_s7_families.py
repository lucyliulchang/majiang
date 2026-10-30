"""S7 规则族：四族注册 + 广东 + 四川（108 张 / 禁吃 / 缺一门 / 血战多赢家）。

柏氏的 07 §13 验收用例在 `test_baishi_s7.py`。

约定：所有引擎都从 `game.families.registry` 取，不直接 new 骨架类
（族差异只通过 capability 与 engine 插件表达，03 §7）。
"""

import pytest

from game.engine import EngineError, SeatState
from game.families import registry
from game.families.guangdong.config import RuleConfig as GuangdongRule
from game.families.sichuan.config import RuleConfig as SichuanRule
from game.tiles import counts_from_tiles


def seats():
    return [
        SeatState(seat=index, login_id=f"1390000000{index}", display_name=f"玩家{index}", color="#C9A063")
        for index in range(4)
    ]


def engine_of(code, rule=None, dealer_seat=0, round_no=1, rng=None):
    config = rule if rule is not None else registry.config_model_of(code)()
    return registry.create_engine(
        code, config, seats(), dealer_seat=dealer_seat, round_no=round_no, rng=rng
    )


def prepare(engine, hand, mapping, turn=0):
    """把四个座位的手牌替换成指定牌面（用于构造局面）。"""
    engine.start_round()
    for seat in range(4):
        engine.seats[seat].counts = counts_from_tiles(hand(mapping.get(seat, "")))
        engine.seats[seat].melds = []
        engine.seats[seat].discards = []
    engine.turn = turn
    engine.phase = "discard"
    engine.claim = None
    engine.last_draw = None
    return engine


# ---------------------------------------------------------------- 四族注册


def test_four_families_listed_and_capability_parsable():
    codes = registry.registered_codes()
    for code in ("generic", "guangdong", "sichuan", "baishi"):
        assert code in codes, code
        plugin = registry.get_family(code)
        assert plugin is not None
        # 自检全过：patterns 已注册、tile_set 可建墙、必备字段齐全
        assert plugin.issues == (), (code, plugin.issues)
        assert plugin.ready is True


def test_every_declared_pattern_is_registered_per_family():
    from game.patterns import registered_ids

    for plugin in registry.all_families():
        visible = set(registered_ids(plugin.rule_family_code))
        for pattern_id in plugin.capability["patterns"]:
            assert pattern_id in visible, (plugin.rule_family_code, pattern_id)


def test_guangdong_drops_thirteen_unrelated():
    capability = registry.capability_of("guangdong")
    assert "thirteen_unrelated" not in capability["patterns"]
    assert capability["patterns"] == ["standard", "seven_pairs", "thirteen_orphans"]
    assert capability["tile_set"] == "136"


def test_sichuan_capability_shape():
    capability = registry.capability_of("sichuan")
    assert capability["tile_set"] == "108"
    assert capability["allow_chow"] is False
    assert capability["lack_suit"] is True
    assert capability["multi_winner"] is True
    assert capability["patterns"] == ["standard", "seven_pairs", "long_seven_pairs"]


def test_baishi_capability_shape():
    capability = registry.capability_of("baishi")
    assert capability["fan_combine"] == ["sum_all"]
    assert capability["fan_cap_allowed"] is False
    assert capability["min_fan_to_win"] == 1
    assert capability["self_draw_multiplier"] == 2
    assert capability["dealer_multiplier"] == {"win": 2, "pay": 2}
    assert capability["bao_pai"]["min_exposed_melds"] == 3
    assert "pause" in capability["switches"]


def test_family_presets_seeded_for_all_four():
    codes = {preset.template_code for plugin in registry.all_families() for preset in plugin.presets}
    assert {"generic_standard", "guangdong_default", "sichuan_default", "baishi_default"} <= codes


# ---------------------------------------------------------------- 广东


def test_guangdong_deals_136(engine_factory):
    engine = engine_of("guangdong")
    engine.start_round()
    assert len(engine.tile_set) == 34
    assert sum(1 for tile in range(34) if tile in engine.tile_set) == 34
    assert sum(engine.seats[0].counts) == 14
    for seat in (1, 2, 3):
        assert sum(engine.seats[seat].counts) == 13
    assert engine.remaining == 136 - 53


def test_guangdong_fan_table_is_twelve_items():
    rule = GuangdongRule()
    assert len(rule.fan_table) == 12
    ids = {item.id for item in rule.fan_table}
    assert "ji_hu" in ids and "peng_peng_hu" in ids and "shi_san_yao" in ids
    # 通用番表的项目不应出现在广东番表里
    assert "men_qian" not in ids and "jian_ke" not in ids
    assert rule.fan_cap == 8


def test_guangdong_ji_hu_and_peng_peng_hu(hand):
    engine = engine_of("guangdong")
    # 平顺：鸡胡 1 + 自摸 1
    prepare(engine, hand, {0: "123m456m789m123p55s"})
    breakdown = engine.evaluate_win(engine._ctx(0, win_tile=18))
    ids = {line.id for line in breakdown.lines}
    assert "ji_hu" in ids
    assert breakdown.fan_total == 2

    engine2 = engine_of("guangdong")
    prepare(engine2, hand, {0: "111m333m555p777s99s"})
    breakdown2 = engine2.evaluate_win(engine2._ctx(0, win_tile=26))
    ids2 = {line.id for line in breakdown2.lines}
    assert "peng_peng_hu" in ids2
    assert "ji_hu" not in ids2  # structure 组取高


def test_guangdong_settlement_conserves(hand):
    engine = prepare(engine_of("guangdong"), hand, {0: "123m456m789m123p55s"})
    engine.last_draw = 18
    engine.apply_action(0, {"action": "hu"})
    settled = engine.result
    assert settled is not None
    assert sum(settled.score_delta) == 0
    assert settled.win_type == "self_draw"
    assert settled.score_delta[0] == 6  # 2 番 × 三家各付


def test_guangdong_template_roundtrip_through_registry():
    preset = {preset.template_code: preset for preset in registry.presets_of("guangdong")}
    config = registry.load_config("guangdong", preset["guangdong_default"].config)
    assert isinstance(config, GuangdongRule)
    assert config.model_dump()["fan_cap"] == 8
    # 族外字段仍然被拒（extra=forbid）
    with pytest.raises(Exception):
        registry.load_config("guangdong", {**preset["guangdong_default"].config, "pause": {"enabled": True}})


# ---------------------------------------------------------------- 四川


def test_sichuan_deals_108(engine_factory):
    engine = engine_of("sichuan")
    engine.start_round()
    assert len(engine.tile_set) == 27
    assert not any(tile in engine.tile_set for tile in range(27, 34))
    assert sum(engine.seats[0].counts) == 14
    assert engine.remaining == 108 - 53


def test_sichuan_rejects_honor_tile(hand):
    engine = prepare(engine_of("sichuan"), hand, {0: "123m456m789m123p1z"})
    with pytest.raises(EngineError) as error:
        engine.apply_action(0, {"action": "discard", "tiles": [27]})
    assert error.value.code == "BAD_DISCARD"


def test_sichuan_cannot_chow(hand):
    engine = prepare(engine_of("sichuan"), hand, {0: "5p", 1: "34m", 2: "12m", 3: "89m"})
    engine.apply_action(0, {"action": "discard", "tiles": [13]})
    window = engine.claim
    # 无人能吃：窗口里只有能碰/胡的座位，没有任何 chow 选项
    for options in (window.options if window else {}).values():
        assert all(option["action"] != "chow" for option in options)
    if window is not None:
        engine.claim = None
        engine.phase = "discard"


def test_sichuan_requires_lack_suit(hand):
    engine = engine_of("sichuan")
    # 三门齐全：不能胡
    prepare(engine, hand, {0: "123m456p789s123m55m"})
    assert engine.evaluate_win(engine._ctx(0, win_tile=0)) is None
    # 缺条：可以胡
    prepare(engine, hand, {0: "123m456m789m123p55p"})
    assert engine.evaluate_win(engine._ctx(0, win_tile=13)) is not None


def test_sichuan_lack_suit_counts_melds(hand):
    from game.hand import Meld

    engine = engine_of("sichuan")
    prepare(engine, hand, {0: "123m456m789m55m"})
    engine.seats[0].melds = [Meld(kind="chow", tiles=[18, 19, 20], from_seat=1)]
    # 手牌万 + 副露条 = 缺筒，只有两门 → 可以胡
    assert engine.evaluate_win(engine._ctx(0, win_tile=4)) is not None


def test_sichuan_hu_does_not_short_circuit_other_seats(hand):
    """血战到底：一家点胡后本局继续，不能把还在犹豫的座位按终态 pass 收掉。"""
    engine = prepare(
        engine_of("sichuan"),
        hand,
        {
            0: "123m456m789m123s55p",  # 14 张，打 5 筒
            1: "123m456m789m11p34p",  # 缺条，听 5 筒（345p + 11p 将）
            2: "55p123m456m789m11s",  # 能碰 5 筒
            3: "123m456m789m123p1s",
        },
    )
    engine.apply_action(0, {"action": "discard", "tiles": [13]})
    window = engine.claim
    assert window is not None and 1 in window.options and 2 in window.options

    engine.apply_action(1, {"action": "hu"})
    assert engine.claim is not None and engine.phase == "claim", "血战里胡不结束本局，不能短路"
    assert not engine.winners

    engine.apply_action(2, {"action": "pass"})
    assert len(engine.winners) == 1
    assert engine.phase != "settled", "还剩两家没胡，牌局继续"


def test_sichuan_two_winners_and_conservation(hand):
    engine = prepare(
        engine_of("sichuan"),
        hand,
        {0: "123m456m789m123p55p", 1: "111p333p555s777s99s"},
    )
    engine.last_draw = 13
    engine.apply_action(0, {"action": "hu"})
    assert engine.phase != "settled", "血战：一胡之后要继续打"
    assert len(engine.winners) == 1

    # 轮到座位 1 自摸：重摆手牌（上一手已经给他摸了一张）
    engine.seats[1].counts = counts_from_tiles(hand("111p333p555s777s99s"))
    engine.seats[1].melds = []
    engine.turn = 1
    engine.phase = "discard"
    engine.last_draw = 26
    engine.apply_action(1, {"action": "hu"})
    assert len(engine.winners) == 2
    assert engine.phase != "settled", "还剩两人没胡，牌局继续"

    # 牌墙摸尽 → 收口成一局两赢家的结算
    engine.front = engine.back + 1
    engine._settle_draw()
    settled = engine.result
    assert settled is not None
    assert len(settled.winners) == 2
    assert [item["seat"] for item in settled.winners] == [0, 1]
    assert sum(settled.score_delta) == 0
    assert settled.is_draw is False


def test_sichuan_winners_stop_paying(hand):
    """已胡的座位不再参与后续赔付：第二家自摸只由在场两家付。"""
    engine = prepare(
        engine_of("sichuan"),
        hand,
        {0: "123m456m789m123p55p", 1: "111p333p555s777s99s"},
    )
    engine.last_draw = 13
    engine.apply_action(0, {"action": "hu"})
    before = list(engine.score_accum)
    engine.seats[1].counts = counts_from_tiles(hand("111p333p555s777s99s"))
    engine.seats[1].melds = []
    engine.turn = 1
    engine.phase = "discard"
    engine.last_draw = 26
    engine.apply_action(1, {"action": "hu"})
    engine.front = engine.back + 1
    engine._settle_draw()
    delta = engine.result.score_delta
    assert delta[0] == before[0], "已胡的座位不该再被扣分"
    assert sum(delta) == 0


def test_sichuan_kong_points(hand):
    from game.hand import Meld

    engine = prepare(engine_of("sichuan"), hand, {0: "555m123p456p789s11s"})
    # 刮风（明杠）：放杠者付 1
    delta = engine._kong_delta(0, "exposed", 2)
    assert delta == [1, 0, -1, 0], "刮风：放杠者独付 1 分"
    assert sum(delta) == 0
    # 下雨（暗杠）：三家各付 2
    hidden = engine._kong_delta(0, "hidden", None)
    assert hidden[0] == 6 and hidden[1] == -2 and hidden[2] == -2 and hidden[3] == -2
    assert sum(hidden) == 0
    assert isinstance(Meld(kind="kong_hidden", tiles=[4] * 4), Meld)


def test_sichuan_cannot_enable_cha_jiao_or_hua_zhu():
    with pytest.raises(Exception):
        SichuanRule(cha_jiao={"enabled": True, "value": 1})
    with pytest.raises(Exception):
        SichuanRule(hua_zhu={"enabled": True, "value": 1})
    rule = SichuanRule()
    assert rule.cha_jiao.enabled is False
    assert rule.hua_zhu.enabled is False


def test_sichuan_forces_lack_suit_and_no_chow():
    with pytest.raises(Exception):
        SichuanRule(allow_chow=True)
    with pytest.raises(Exception):
        SichuanRule(lack_suit_required=False)


def test_sichuan_long_seven_pairs_pattern_triggered(hand):
    # 4 张相同算两对：1111m 22m 33m 44p 55p 66p → 七对 + 龙七对（两门，满足缺一门）
    engine = prepare(engine_of("sichuan"), hand, {0: "1111m22m33m44p55p66p"})
    wins = engine.evaluate_win(engine._ctx(0, win_tile=19))
    ids = {line.id for line in wins.lines}
    # 龙七对与七对同组（special），取高不叠加
    assert "long_qi_dui" in ids
    assert "qi_dui" not in ids
    assert wins.fan_total >= 8
