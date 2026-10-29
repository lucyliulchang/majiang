"""柏氏规则族 `baishi` 按 07 §13 的验收用例（30 条 + 16b/16c）。

组织方式：
- 番种类用例直接构造 `HandContext` 求番（`_eval`），断言**番种命中**与**番合计**；
- 结算类用例走引擎的 `_settle_fan_delta` / `_finish_win`，断言四家分差与付款方分配；
- 牌路类用例（抢杠、补杠、暗杠、荒庄、发牌）走真实引擎状态机。

口径提醒（07 §5 的两条"恒可累加"）：
`门清`（1 番）与 `将牌`（1 番）不属于任何互斥组，只要成立就必须计。
因此 07 §13 里个别"基准番"数字（如"全文字 + 四暗刻 = 120"）是**组内求和**的口径，
本文件对这类用例同时断言"组内和"与"含必须累加项后的总数"，并在断言旁注明算式。
"""

from __future__ import annotations

import pytest

from game.engine import EngineError, SeatState
from game.families import registry
from game.families.baishi import selfcheck
from game.families.baishi.config import BaishiKongScore, RuleConfig
from game.families.baishi.fan import FAN_TABLE, FAN_VALUES
from game.fan import ScoreBreakdown, FanLine, best_win
from game.hand import HandContext, Meld
from game.patterns import collect_wins
from game.tiles import counts_from_tiles

RULE = RuleConfig()


def seats():
    return [
        SeatState(seat=index, login_id=f"1370000000{index}", display_name=f"柏{index}", color="#C9A063")
        for index in range(4)
    ]


def engine(rule=None, dealer_seat=0, round_no=1):
    return registry.create_engine(
        "baishi", rule or RuleConfig(), seats(), dealer_seat=dealer_seat, round_no=round_no
    )


def pong(tile, seat=1):
    return Meld(kind="pong", tiles=[tile] * 3, from_seat=seat)


def chow(tile, seat=1):
    return Meld(kind="chow", tiles=[tile, tile + 1, tile + 2], from_seat=seat)


def kong(tile, kind="kong_hidden"):
    return Meld(kind=kind, tiles=[tile] * 4)


def ctx_of(hand, text, win_tile=None, melds=None, seat_wind=0, round_wind=0, **flags):
    return HandContext(
        counts=counts_from_tiles(hand(text)),
        melds=list(melds or []),
        win_tile=win_tile,
        is_self_draw=flags.pop("is_self_draw", False),
        seat_wind=seat_wind,
        round_wind=round_wind,
        **flags,
    )


def _eval(ctx, rule=None):
    target = rule or RULE
    return best_win(collect_wins(ctx, target), target)


def ids_of(breakdown) -> dict[str, int]:
    return {line.id: line.fan * line.count for line in breakdown.lines}


def fan_ids(ctx) -> dict[str, int]:
    """求番；不成胡（没有命中任何牌型）时返回空字典。"""
    breakdown = _eval(ctx)
    return {} if breakdown is None else ids_of(breakdown)


def fake_breakdown(fan_total: int, rule=None) -> ScoreBreakdown:
    """只用于结算用例：跳过番种判定，直接给一个番合计。"""
    target = rule or RULE
    return ScoreBreakdown(
        pattern_id="standard",
        pattern_name="标准胡",
        lines=[FanLine(id="ping_hu", name="平胡", fan=fan_total)],
        fan_raw=fan_total,
        fan_total=fan_total,
        score=fan_total * target.base_score,
    )


# ---------------------------------------------------------------- 番表与 capability


def test_baishi_fan_table_matches_07_section_5():
    assert len(RULE.fan_table) == 31
    assert len(FAN_TABLE) == 31
    for fan_id, name, fan, group, _counting in FAN_TABLE:
        item = RULE.fan_of(fan_id)
        assert item is not None, fan_id
        assert item.name == name
        assert item.fan == fan, fan_id
        assert item.exclusive_group == group, fan_id
    # 番表里没有「杠」项（杠只计分，07 §8）
    assert RULE.fan_of("gang") is None
    assert FAN_VALUES["quan_zi_qi_dui"] == 120


def test_baishi_default_config_matches_07_section_10():
    config = RuleConfig()
    assert config.fan_combine == "sum_all"
    assert config.fan_cap is None
    assert config.fan_mode == "linear"
    assert config.min_fan_to_win == 1
    assert config.self_draw_multiplier == 2
    assert config.dealer_rule.win_multiplier == 2
    assert config.dealer_rule.pay_multiplier == 2
    assert config.discard_pay_mode == "all"
    assert config.bao_pai.enabled is True
    assert config.bao_pai.min_exposed_melds == 3
    assert config.kong_score.pay_mode == "all"
    assert config.turn_timeout.enabled is False
    assert config.pause.enabled is True
    assert config.rounds_per_game == 4


def test_baishi_fan_cap_not_allowed():
    capability = registry.capability_of("baishi")
    assert capability["fan_cap_allowed"] is False
    assert capability["fan_cap_max"] == 0


def test_baishi_rejects_fan_cap_through_rule_service():
    """族能力白名单在 ruleService 层拒绝封顶（07 §11 `fan_cap_allowed=false`）。"""
    from processor import ruleService

    with pytest.raises(ruleService.RuleServiceError) as error:
        ruleService.validateConfig("baishi", {"fan_cap": 8})
    assert error.value.code == "RULE_FAN_CAP_UNSUPPORTED"


# ---------------------------------------------------------------- 13.1 对对胡 + 清一色


def baishi_qingyise_duidui(hand):
    """3 组明刻 + 1 组暗刻 + 将 4 万：对对胡 10 + 清一色 30 = 40（无暗刻番、将非 258）。"""
    melds = [pong(0), pong(2), pong(4)]
    return ctx_of(hand, "777m44m", win_tile=6, melds=melds)


def test_case01_duidui_plus_qingyise_is_40(hand):
    breakdown = _eval(baishi_qingyise_duidui(hand))
    ids = ids_of(breakdown)
    assert ids["dui_dui_hu"] == 10
    assert ids["qing_yi_se"] == 30
    assert "san_an_ke" not in ids and "si_an_ke" not in ids
    assert breakdown.fan_total == 40
    # 不封顶：U = base × 40
    assert breakdown.score == 40


# ---------------------------------------------------------------- 13.2 - 13.6 倍数与包牌


def test_case02_non_dealer_self_draw_41(hand):
    eng = engine(dealer_seat=0)
    delta, allocation, multipliers = eng._settle_fan_delta(
        1, fake_breakdown(41), "self_draw", None
    )
    assert delta == [-164, 328, -82, -82]
    assert sum(delta) == 0
    assert allocation == []
    assert multipliers == {"self_draw": 2, "dealer": 2}


def test_case03_dealer_self_draw_20(hand):
    eng = engine(dealer_seat=0)
    delta, _allocation, _multipliers = eng._settle_fan_delta(
        0, fake_breakdown(20), "self_draw", None
    )
    assert delta == [240, -80, -80, -80]


def test_case04_non_dealer_ron_20(hand):
    eng = engine(dealer_seat=0)
    delta, allocation, _multipliers = eng._settle_fan_delta(
        1, fake_breakdown(20), "discard", 2
    )
    # 点炮三家各付：庄家 ×2、另两家 ×1
    assert delta == [-40, 80, -20, -20]
    assert allocation == []
    assert sum(delta) == 0


def test_case05_bao_pai_with_three_exposed_melds(hand):
    eng = engine(dealer_seat=0)
    ctx = baishi_qingyise_duidui(hand)
    breakdown = _eval(ctx)
    assert breakdown.fan_total == 40
    delta, allocation, _multipliers = eng._settle_fan_delta(
        1, breakdown, "discard", 2, ctx, 6
    )
    # 庄 80 + 点炮者 40 + 另一闲 40 = 160，全由点炮者承担
    assert delta == [0, 160, -160, 0]
    assert sum(delta) == 0
    assert len(allocation) == 1
    record = allocation[0]
    assert record["reason"] == "bao_pai"
    assert record["bao_pai_seat"] == 2
    assert record["amount"] == 160
    assert record["covered"] == [0, 3]
    assert "qing_yi_se" in record["patterns"]


def test_case05b_bao_pai_needs_tile_in_allowed_set(hand):
    """3 明牌混一色，但点炮牌是另一门花色 → 不包（07 §7.4）。"""
    eng = engine(dealer_seat=0)
    melds = [pong(0), pong(1), pong(27)]  # 1 万 / 2 万 / 东 → 万 + 字
    ctx = ctx_of(hand, "456m55m", win_tile=3, melds=melds)
    breakdown = _eval(ctx)
    assert "hun_yi_se" in ids_of(breakdown)
    delta, allocation, _multipliers = eng._settle_fan_delta(
        1, breakdown, "discard", 2, ctx, 22
    )
    assert allocation == []
    assert sum(delta) == 0


def test_case05c_bao_pai_needs_three_exposed_melds(hand):
    eng = engine(dealer_seat=0)
    melds = [pong(0), pong(2)]
    ctx = ctx_of(hand, "777m444p44m", win_tile=6, melds=melds)
    breakdown = _eval(ctx)
    assert breakdown is not None
    assert len(ctx.exposed_melds) == 2
    delta, allocation, _multipliers = eng._settle_fan_delta(
        1, breakdown, "discard", 2, ctx, 6
    )
    assert allocation == []


def test_case06_self_draw_never_bao(hand):
    eng = engine(dealer_seat=0)
    ctx = baishi_qingyise_duidui(hand)
    breakdown = _eval(ctx)
    delta, allocation, _multipliers = eng._settle_fan_delta(1, breakdown, "self_draw", None, ctx, 6)
    assert allocation == []
    # 40 × 自摸 2 × 庄家 2 = 160（庄），另两家各 80
    assert delta == [-160, 320, -80, -80]
    assert sum(delta) == 0


def test_case08_tian_hu_100(hand):
    ctx = ctx_of(hand, "123m456m789m123p55s", win_tile=18, is_self_draw=True, is_heavenly=True)
    breakdown = _eval(ctx)
    ids = ids_of(breakdown)
    assert ids["tian_hu"] == 100
    assert "men_qian" not in ids, "天胡不叠加门清（07 §5 first 组）"

    eng = engine(dealer_seat=0)
    delta, _allocation, _multipliers = eng._settle_fan_delta(0, fake_breakdown(100), "self_draw", None)
    assert delta == [1200, -400, -400, -400]


def test_case08b_di_hu_for_non_dealer(hand):
    ctx = ctx_of(hand, "123m456m789m123p55s", win_tile=18, is_self_draw=True, is_earthly=True)
    ids = ids_of(_eval(ctx))
    assert ids["di_hu"] == 50
    assert "men_qian" not in ids


# ---------------------------------------------------------------- 13.7 海底


def test_case07_hai_di_only_on_last_one_dot(hand):
    ctx = ctx_of(
        hand, "123m456m789m123p55s", win_tile=9, is_self_draw=True, is_last_tile=True
    )
    # 1 筒 = 9 号牌；海底只看"最后一张 + 自摸"，与胡的是哪张无关
    ids = ids_of(_eval(ctx))
    assert ids["hai_di_lao_yue"] == 100

    ctx2 = ctx_of(
        hand, "123m456m789m123p55p", win_tile=10, is_self_draw=True, is_last_tile=True
    )
    assert "hai_di_lao_yue" not in ids_of(_eval(ctx2))


# ---------------------------------------------------------------- 13.9 13不靠


def test_case09_thirteen_unrelated_positive(hand):
    # 中发白齐 + 三门数牌各 3 张同组（147 万 / 258 筒 / 369 条）+ 将 9 万
    breakdown = _eval(ctx_of(hand, "147m258p369s5z6z7z9m9m", win_tile=26))
    ids = ids_of(breakdown)
    assert ids["shi_san_bu_kao"] == 10
    assert ids["jiang_pai"] == 1, "13不靠 也判将牌"
    assert ids["du_ying"] == 1, "13不靠 必为单吊，判独赢"


def test_case09_thirteen_unrelated_jang_five_dot(hand):
    breakdown = _eval(ctx_of(hand, "147m258p369s5z6z7z5p5p", win_tile=13))
    ids = ids_of(breakdown)
    assert ids["shi_san_bu_kao"] == 10
    assert ids["jiang_pai"] == 1


@pytest.mark.parametrize(
    "text",
    [
        "148m258p369s5z6z7z9m9m",  # 同门跨组（1/8）
        "124m258p369s5z6z7z9m9m",  # 同门相邻（1/2/4）
        "147m258p369s4z4z4z9m9m",  # 缺中发白、混入北风
        "125m258p369s5z6z7z9m9m",  # 1/5 跨组
        "147m258p369s5z6z7z",  # 只有 13 张
    ],
)
def test_case09_thirteen_unrelated_negative(hand, text):
    assert "shi_san_bu_kao" not in fan_ids(ctx_of(hand, text, win_tile=26))


# ---------------------------------------------------------------- 13.10 七小对


def test_case10_seven_pairs_with_quad(hand):
    breakdown = _eval(ctx_of(hand, "1111m2233p4455s66s", win_tile=23))
    ids = ids_of(breakdown)
    assert ids["qi_xiao_dui"] == 20
    assert "long_qi_dui" not in ids, "柏氏不设豪华七对"
    assert "dui_dui_hu" not in ids, "structure 组取高"


# ---------------------------------------------------------------- 13.11 青龙上位


def test_case11_qing_long_suppresses_lian_liu(hand):
    breakdown = _eval(ctx_of(hand, "123m456m789m123m44m", win_tile=5))
    ids = ids_of(breakdown)
    assert ids["qing_long"] == 20
    assert "lian_liu" not in ids
    assert "lao_shao_fu" not in ids
    assert "yi_ban_gao" not in ids
    assert ids["qing_yi_se"] == 30
    assert ids["ping_hu"] == 1, "4 顺 + 将且非嵌张 → 平胡与青龙不同组，可叠"
    assert breakdown.fan_total == 52  # 20 + 30 + 门清 1 + 平胡 1


def test_case11b_hun_long(hand):
    breakdown = _eval(ctx_of(hand, "123m456m789p123m44m", win_tile=5))
    ids = ids_of(breakdown)
    assert ids["hun_long"] == 10
    assert "qing_long" not in ids


# ---------------------------------------------------------------- 13.12 开关


def test_case12_kong_score_disabled_gives_zero(hand):
    rule = RuleConfig(kong_score=BaishiKongScore(enabled=False))
    eng = engine(rule)
    for kind in ("exposed", "hidden", "added"):
        assert eng._kong_delta(1, kind, 2) == [0, 0, 0, 0]
    assert rule.turn_timeout.enabled is False, "柏氏默认不限时，快照不下发 deadline"


def test_case12b_kong_points_are_three_payers(hand):
    eng = engine()
    assert eng._kong_delta(1, "exposed", 2) == [-1, 3, -1, -1]
    assert eng._kong_delta(1, "hidden", None) == [-2, 6, -2, -2]
    assert eng._kong_delta(1, "added", None) == [-1, 3, -1, -1]
    for kind in ("exposed", "hidden", "added"):
        assert sum(eng._kong_delta(1, kind, 2)) == 0


# ---------------------------------------------------------------- 13.14 暗刻


def test_case14_duidui_plus_san_an_ke_is_20(hand):
    melds = [pong(0)]
    breakdown = _eval(ctx_of(hand, "777m333p555s66s", win_tile=6, melds=melds))
    ids = ids_of(breakdown)
    assert ids["dui_dui_hu"] == 10
    assert ids["san_an_ke"] == 10
    assert "si_an_ke" not in ids
    assert breakdown.fan_total == 20


def test_case14b_duidui_plus_si_an_ke(hand):
    melds = [kong(0)]
    breakdown = _eval(ctx_of(hand, "777m333p555s66s", win_tile=6, melds=melds))
    ids = ids_of(breakdown)
    assert ids["dui_dui_hu"] == 10
    assert ids["si_an_ke"] == 20
    assert "san_an_ke" not in ids, "四暗刻不叠加三暗刻"
    # 07 §13 的「30」是组内和；四暗刻必为全暗手，门清 1 恒可累加（07 §5）
    assert ids["men_qian"] == 1
    assert breakdown.fan_total == 31


# ---------------------------------------------------------------- 13.15 缺门


def test_case15_que_men_only_for_non_flush(hand):
    two_suits = ids_of(_eval(ctx_of(hand, "123m456m789m123p55p", win_tile=13)))
    assert two_suits["que_men"] == 1

    clean = ids_of(_eval(ctx_of(hand, "123m456m789m123m55m", win_tile=13)))
    assert clean["qing_yi_se"] == 30
    assert "que_men" not in clean

    mixed = ids_of(_eval(ctx_of(hand, "111m999m1z1z1z5z5z5z9m9m", win_tile=26)))
    assert mixed["hun_yi_se"] == 20
    assert "que_men" not in mixed

    quan_yao = ids_of(_eval(ctx_of(hand, "111m999p111s1z1z1z1z1z", win_tile=27)))
    assert "quan_yao" in quan_yao
    assert "que_men" not in quan_yao

    quan_zi = ids_of(_eval(ctx_of(hand, "1z1z1z2z2z2z3z3z3z4z4z4z5z5z", win_tile=31)))
    assert "quan_zi" in quan_zi
    assert "que_men" not in quan_zi

    orphans = ids_of(_eval(ctx_of(hand, "19m19p19s1234567z1z", win_tile=27)))
    assert "shi_san_yao" in orphans
    assert "que_men" not in orphans


# ---------------------------------------------------------------- 13.17 将牌


def test_case17_jiang_pai(hand):
    five_dot = ids_of(_eval(ctx_of(hand, "123m456m789m123p55p", win_tile=13)))
    assert five_dot["jiang_pai"] == 1

    east = ids_of(_eval(ctx_of(hand, "123m456m789m123p1z1z", win_tile=27)))
    assert east["jiang_pai"] == 1

    three_wan = ids_of(_eval(ctx_of(hand, "123m234m33m456p789s", win_tile=3)))
    assert "jiang_pai" not in three_wan

    seven_pairs = ids_of(_eval(ctx_of(hand, "11m33m55m77m99m11p22p", win_tile=10)))
    assert "jiang_pai" not in seven_pairs, "七小对不判将牌"


# ---------------------------------------------------------------- 13.18 / 13.24 顺子类


def test_case18_yi_ban_gao(hand):
    # 234 万 + 234 筒：异花色同数序 → 一般高 1（避开 123/456/789 的龙）
    breakdown = _eval(ctx_of(hand, "234m234p567s678s99s", win_tile=22))
    ids = ids_of(breakdown)
    assert ids["yi_ban_gao"] == 1
    assert "zi_mei_hua" not in ids
    assert "hun_long" not in ids and "qing_long" not in ids


def test_case18b_zi_mei_hua(hand):
    # 234 万 ×2：同花色同数序 → 姊妹花 2
    breakdown = _eval(ctx_of(hand, "234m234m567p678s99s", win_tile=22))
    ids = ids_of(breakdown)
    assert ids["zi_mei_hua"] == 2
    assert "yi_ban_gao" not in ids


def test_case18c_san_zi_mei(hand):
    """三姊妹固定 3 番，替代这 3 对的姊妹花/一般高。

    三副同数序顺子必然也能拆成三副刻子，而「逐解求番取最高」（07 §6.1）会让
    暗刻解胜出；因此这里直接对顺子类求番，锁定三姊妹本身的番值与抑制关系。
    """
    from game.families.baishi.fan import chow_fans

    hits = {hit.id: hit.count for hit in chow_fans([3, 3, 3])}  # 234万 ×3
    assert hits == {"san_zi_mei": 1}
    assert "zi_mei_hua" not in hits and "yi_ban_gao" not in hits


def test_case24_each_pair_counted_once(hand):
    # 234万×2 + 234条：姊妹花 1 对（2 番）+ 一般高 2 对（1×2）= 4
    from game.families.baishi.fan import chow_fans

    hits = {hit.id: hit.count for hit in chow_fans([3, 3, 12])}
    assert hits["zi_mei_hua"] == 1
    assert hits["yi_ban_gao"] == 2
    assert hits["zi_mei_hua"] * 2 + hits["yi_ban_gao"] * 1 == 4


# ---------------------------------------------------------------- 13.19 平胡


def test_case19_ping_hu(hand):
    breakdown = _eval(ctx_of(hand, "234m345p567s678s33m", win_tile=1))
    ids = ids_of(breakdown)
    assert ids["ping_hu"] == 1
    assert ids["men_qian"] == 1
    assert "du_ying" not in ids
    assert "jiang_pai" not in ids
    assert breakdown.fan_total == 2


def test_case19b_ping_hu_breaks_with_258_pair(hand):
    breakdown = _eval(ctx_of(hand, "234m345p567s678s55m", win_tile=1))
    ids = ids_of(breakdown)
    assert "ping_hu" not in ids
    assert ids["jiang_pai"] == 1


# ---------------------------------------------------------------- 13.20 独赢


def test_case20_du_ying_forms(hand):
    kan = ids_of(_eval(ctx_of(hand, "123m234p345s567s55s", win_tile=1)))
    assert kan["du_ying"] == 1, "嵌张 1_3 赢 2"

    single = ids_of(_eval(ctx_of(hand, "234m234p345s678s55m", win_tile=4)))
    assert single["du_ying"] == 1, "单吊将"

    penchan = ids_of(_eval(ctx_of(hand, "789m234p345s567s55s", win_tile=6)))
    assert penchan["du_ying"] == 1, "89 赢 7 是单边"

    ryanmen = ids_of(_eval(ctx_of(hand, "234m234p345s567s55s", win_tile=1)))
    assert "du_ying" not in ryanmen, "23 赢 1 是两面"


# ---------------------------------------------------------------- 13.21 全幺


def test_case21_quan_yao(hand):
    breakdown = _eval(ctx_of(hand, "111m999p111s1z1z1z1z1z", win_tile=27))
    ids = ids_of(breakdown)
    assert ids["quan_yao"] == 50
    assert "dui_dui_hu" not in ids, "quan 组命中时 structure 不计"
    assert ids["jiang_pai"] == 1


def test_case21b_quan_yao_plus_hun_yi_se_is_70(hand):
    breakdown = _eval(ctx_of(hand, "111m999m1z1z1z2z2z2z9m9m", win_tile=26))
    ids = ids_of(breakdown)
    assert ids["quan_yao"] == 50
    assert ids["hun_yi_se"] == 20
    assert ids["quan_yao"] + ids["hun_yi_se"] == 70
    assert "que_men" not in ids


def test_case21c_quan_yao_plus_hun_yi_se_plus_si_an_ke(hand):
    melds = [kong(0), kong(8), kong(27), kong(31)]
    breakdown = _eval(ctx_of(hand, "9m9m", win_tile=26, melds=melds))
    ids = ids_of(breakdown)
    assert ids["quan_yao"] == 50
    assert ids["hun_yi_se"] == 20
    assert ids["si_an_ke"] == 20
    assert ids["quan_yao"] + ids["hun_yi_se"] + ids["si_an_ke"] == 90
    assert "dui_dui_hu" not in ids


def test_case21d_quan_yao_qi_dui_is_60(hand):
    breakdown = _eval(ctx_of(hand, "11m99m11p99p1z1z5z5z9s9s", win_tile=31))
    ids = ids_of(breakdown)
    assert ids["quan_yao_qi_dui"] == 60
    assert "qi_xiao_dui" not in ids
    assert "dui_dui_hu" not in ids


# ---------------------------------------------------------------- 13.22 全文字


def test_case22_quan_zi_is_101(hand):
    melds = [pong(31), pong(32)]
    breakdown = _eval(ctx_of(hand, "3z3z3z4z4z4z7z7z", win_tile=29, melds=melds))
    ids = ids_of(breakdown)
    assert ids["quan_zi"] == 100
    assert ids["jiang_pai"] == 1
    assert "dui_dui_hu" not in ids
    assert breakdown.fan_total == 101


def test_case22b_quan_zi_plus_si_an_ke(hand):
    breakdown = _eval(ctx_of(hand, "2z2z2z3z3z3z4z4z4z5z5z5z6z6z", win_tile=28))
    ids = ids_of(breakdown)
    assert ids["quan_zi"] == 100
    assert ids["si_an_ke"] == 20
    assert ids["quan_zi"] + ids["si_an_ke"] == 120
    assert ids["men_qian"] == 1
    assert breakdown.fan_total == 122  # 100 + 20 + 将 1 + 门清 1


def test_case22c_quan_zi_seven_pairs(hand):
    breakdown = _eval(ctx_of(hand, "1z1z2z2z3z3z4z4z5z5z6z6z7z7z", win_tile=33))
    ids = ids_of(breakdown)
    assert ids["quan_zi_qi_dui"] == 120
    assert ids["du_ying"] == 1, "全文字七对可叠独赢"
    assert "jiang_pai" not in ids, "七对不判将牌"


# ---------------------------------------------------------------- 13.23 十三幺


def test_case23_thirteen_orphans_is_102(hand):
    breakdown = _eval(ctx_of(hand, "19m19p19s1234567z1z", win_tile=27))
    ids = ids_of(breakdown)
    assert ids["shi_san_yao"] == 100
    assert ids["jiang_pai"] == 1
    assert ids["men_qian"] == 1
    assert "du_ying" not in ids, "十三幺不判独赢"
    assert breakdown.fan_total == 102


# ---------------------------------------------------------------- 13.25 - 13.27 风刻


def test_case25_wind_ke_stacking(hand):
    # 庄家（门风东）+ 第 1 局（局风东）持东刻子 → 门风刻 1 + 圈风刻 1
    breakdown = _eval(
        ctx_of(hand, "1z1z1z123m456p789s5p5p", win_tile=4, seat_wind=0, round_wind=0)
    )
    ids = ids_of(breakdown)
    assert ids["men_feng_ke"] == 1
    assert ids["quan_feng_ke"] == 1

    # 同一手改持南刻子 → 0
    south = ids_of(
        _eval(ctx_of(hand, "2z2z2z123m456p789s5p5p", win_tile=4, seat_wind=0, round_wind=0))
    )
    assert "men_feng_ke" not in south and "quan_feng_ke" not in south

    # 第 2 局（局风南）庄家持东刻子 → 仅门风刻
    second = ids_of(
        _eval(ctx_of(hand, "1z1z1z123m456p789s5p5p", win_tile=4, seat_wind=0, round_wind=1))
    )
    assert second["men_feng_ke"] == 1
    assert "quan_feng_ke" not in second


def test_case26_wind_ke_cross_wind(hand):
    # 门风为南（seat_wind=1）在东风局（round_wind=0）持南南南 + 东东东
    breakdown = _eval(
        ctx_of(hand, "2z2z2z1z1z1z123m456p5p5p", win_tile=4, seat_wind=1, round_wind=0)
    )
    ids = ids_of(breakdown)
    assert ids["men_feng_ke"] == 1
    assert ids["quan_feng_ke"] == 1


def test_case27_wind_pair_is_not_ke(hand):
    breakdown = _eval(
        ctx_of(hand, "1z1z123m456m789m123p", win_tile=4, seat_wind=0, round_wind=0)
    )
    ids = ids_of(breakdown)
    assert "men_feng_ke" not in ids
    assert "quan_feng_ke" not in ids
    assert ids["jiang_pai"] == 1


# ---------------------------------------------------------------- 13.30 发牌


def test_case30_deal_shape(hand):
    eng = engine()
    eng.start_round()
    assert len(eng.tile_set) == 34
    assert sum(eng.seats[0].counts) == 14
    for seat in (1, 2, 3):
        assert sum(eng.seats[seat].counts) == 13
    assert eng.remaining == 136 - 53
    assert eng.turn == 0 and eng.phase == "discard"


# ---------------------------------------------------------------- 13.28 / 13.29 荒庄


def test_case28_draw_without_kong_restarts_same_round():
    eng = engine(round_no=2, dealer_seat=1)
    eng.start_round()
    round_no, dealer, wind = eng.round_no, eng.dealer_seat, eng.round_wind
    eng.front = eng.back + 1
    events = eng._settle_draw()
    assert eng.result is None, "无杠荒庄不落库"
    assert eng.round_no == round_no
    assert eng.dealer_seat == dealer
    assert eng.round_wind == wind
    assert any(event["type"] == "event.round_restarted" for event in events)


def test_case29_draw_with_kong_settles_as_draw():
    eng = engine(round_no=2, dealer_seat=1)
    eng.start_round()
    eng.kong_happened = True
    eng.kong_accumulated = [-1, 3, -1, -1]
    eng.front = eng.back + 1
    eng._settle_draw()
    settled = eng.result
    assert settled is not None
    assert settled.winner_seat is None
    assert settled.is_draw is True
    assert settled.score_delta == [-1, 3, -1, -1], "杠分保留、不罚分"
    assert settled.winners == []


# ---------------------------------------------------------------- 13.16 抢杠（明杠）


def prepare(eng, hand, mapping, turn=0):
    eng.start_round()
    for seat in range(4):
        eng.seats[seat].counts = counts_from_tiles(hand(mapping.get(seat, "")))
        eng.seats[seat].melds = []
        eng.seats[seat].discards = []
    eng.turn = turn
    eng.phase = "discard"
    eng.claim = None
    eng.last_draw = None
    return eng


def test_case16_exposed_kong_can_be_robbed(hand):
    eng = prepare(
        engine(dealer_seat=0),
        hand,
        {
            0: "7m 1p2p3p4p5p6p7p8p9p1s2s3s",  # 点炮者
            1: "7m7m7m 1p2p3p4p5p6p7p8p9p1s",  # 手里 3 张 7 万，声明明杠
            2: "56m 1p 9p 1s2s3s 33m",  # 吃碰各一的听牌手（明刻 1 筒）
        },
    )
    eng.seats[2].melds = [pong(9)]
    eng.seats[2].counts = counts_from_tiles(hand("56m 55m 1s2s3s 456p"))  # 将 5 万，1 番起胡
    eng.apply_action(0, {"action": "discard", "tiles": [6]})
    window = eng.claim
    assert window is not None
    assert window.reason == "discard"
    assert 1 in window.options and 2 in window.options
    # 窗口要等所有有选项的座位都应答；座位 2 先放弃点炮胡（胡 > 碰/杠）
    eng.apply_action(2, {"action": "pass"})
    # 座位 1 声明明杠 → 立刻开抢杠窗口（而不是直接成杠）
    eng.apply_action(1, {"action": "kong", "tiles": [6]})
    rob = eng.claim
    assert rob is not None and rob.reason == "rob_kong"
    assert rob.kong_seat == 1 and rob.kong_kind == "exposed"
    assert 2 in rob.options
    assert any(option["action"] == "hu" for option in rob.options[2])

    eng.apply_action(2, {"action": "hu"})
    settled = eng.result
    assert settled is not None
    assert settled.win_type == "rob_kong"
    assert settled.winner_seat == 2
    ids = {item["id"] for item in settled.fan_items}
    assert "qiang_gang_hu" in ids
    assert settled.fan_total == 11, "抢杠胡 10 + 将牌 1（本手无门清/独赢）"
    # 三家各付、不乘自摸倍数；庄家那份 ×2（07 §3.2）
    assert settled.score_delta == [-22, -11, 44, -11]
    assert sum(settled.score_delta) == 0
    assert settled.payer_allocation == [], "抢杠胡不触发包牌"
    assert settled.kong_delta == [0, 0, 0, 0], "被抢的明杠作废、不计杠分"
    assert not any(meld.kind == "kong_exposed" for meld in eng.seats[1].melds)


def test_case16_exposed_kong_stands_when_nobody_robs(hand):
    eng = prepare(
        engine(dealer_seat=0),
        hand,
        {
            0: "7m 1p2p3p4p5p6p7p8p9p1s2s3s",
            1: "7m7m7m 1p2p3p4p5p6p7p8p9p1s",
            2: "456m789m56m123p55s",  # 可抢 7 万（门清 1 + 将 5 条 1）
            3: "2p2p2p3p3p3p4p4p4p5s6s7s8s",
        },
    )
    eng.apply_action(0, {"action": "discard", "tiles": [6]})
    assert 2 in eng.claim.options, "座位 2 能抢这张杠（否则不会开窗口）"
    eng.apply_action(2, {"action": "pass"})  # 放弃点炮胡，明杠才进入仲裁
    eng.apply_action(1, {"action": "kong", "tiles": [6]})
    rob = eng.claim
    assert rob is not None and rob.reason == "rob_kong"
    assert 1 not in rob.options, "杠家本人不进抢杠窗口"
    for seat in list(rob.options):
        eng.apply_action(seat, {"action": "pass"})
    assert any(meld.kind == "kong_exposed" for meld in eng.seats[1].melds)
    assert eng.kong_accumulated[1] == 3, "明杠 1 分三家各付"


def test_case16b_added_kong_cannot_be_robbed(hand):
    eng = prepare(
        engine(dealer_seat=0),
        hand,
        {
            0: "1p2p3p4p5p6p7p8p9p1s2s3s4s",
            1: "7m 1p2p3p4p5p6p7p8p9p1s2s",  # 碰过 7 万，摸到第 4 张
            2: "56m 33m 1s2s3s 456p",
            3: "2p2p2p3p3p3p4p4p4p5s6s7s8s",
        },
        turn=1,
    )
    eng.seats[1].melds = [pong(6)]
    eng.seats[1].counts = counts_from_tiles(hand("7m 123456789p 12s"))
    eng.last_draw = 6
    events = eng.apply_action(1, {"action": "kong", "tiles": [6], "kong_kind": "added"})
    assert eng.claim is None, "补杠不开放抢杠窗口"
    assert any(meld.kind == "kong_added" for meld in eng.seats[1].melds)
    assert eng.kong_accumulated[1] == 3, "补杠 1 分三家各付"
    assert any(event["type"] == "event.kongged" for event in events)
    assert eng.phase == "discard"


def test_case16c_hidden_kong_cannot_be_robbed(hand):
    eng = prepare(
        engine(dealer_seat=0),
        hand,
        {
            0: "1p2p3p4p5p6p7p8p9p1s2s3s4s",
            1: "7m7m7m7m 123456789p 12s",
            2: "56m 33m 1s2s3s 456p",
            3: "2p2p2p3p3p3p4p4p4p5s6s7s8s",
        },
        turn=1,
    )
    eng.last_draw = 6
    eng.apply_action(1, {"action": "kong", "tiles": [6], "kong_kind": "hidden"})
    assert eng.claim is None
    assert any(meld.kind == "kong_hidden" for meld in eng.seats[1].melds)
    assert eng.kong_accumulated[1] == 6, "暗杠 2 分三家各付"


# ---------------------------------------------------------------- 就绪门禁


def test_baishi_ready_after_acceptance():
    plugin = registry.get_family("baishi")
    assert plugin is not None
    assert selfcheck.PENDING_CHECKS == ()
    assert plugin.ready is True


def test_baishi_blocks_table_before_acceptance(monkeypatch):
    """07 §13 用例未全绿时：族可列、模板可读，但开桌必须 RULE_FAMILY_NOT_READY。"""
    from game.families import baishi

    pending = ("07-13-01", "07-13-16b")
    blocked = registry.register_family(baishi.build_plugin(pending))
    try:
        assert blocked.ready is False
        assert len(blocked.issues) == len(pending)
        assert all("07 §13" in issue for issue in blocked.issues)
        with pytest.raises(registry.FamilyError) as error:
            registry.create_engine("baishi", RuleConfig(), seats())
        assert error.value.code == "RULE_FAMILY_NOT_READY"
    finally:
        registry.register_family(baishi.build_plugin())
    assert registry.get_family("baishi").ready is True


# ---------------------------------------------------------------- 暂停（07 §9）


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


def build_baishi_actor(s5_env):
    from realtime.room import RoomActor

    room = s5_env["room"]
    config = RuleConfig()
    snapshot = {
        "rule_family_code": "baishi",
        "template_id": s5_env["template_id"],
        "config": config.model_dump(),
    }
    actor = RoomActor(
        code=room["room_code"],
        room_id=room["id"],
        family_id=s5_env["family_id"],
        family_code=s5_env["family_code"],
        family_name="S5 测试家庭",
        name="柏氏测试房",
        host_login_id=s5_env["owner"],
        rule=config,
        rule_name="柏氏标准",
        rule_snapshot=snapshot,
    )
    sockets = {}
    for loginID in s5_env["members"]:
        ws = FakeWS()
        sockets[loginID] = ws
        actor.attach(loginID, ws)
        actor.assign(loginID, f"玩家{loginID[-1]}", "#C9A063")
    return actor, sockets


async def test_baishi_pause_and_resume(s5_env):
    actor, sockets = build_baishi_actor(s5_env)
    owner = s5_env["owner"]
    other = s5_env["members"][1]
    try:
        for loginID in s5_env["members"]:
            await actor.handle(loginID, {"type": "seat.ready", "data": {}})
        await actor.handle(owner, {"type": "game.start", "data": {}})

        await actor.handle(owner, {"type": "room.pause", "data": {"note": "接个电话"}})
        assert actor.paused is True
        assert actor.paused_by_login_id == owner
        assert actor.turn_deadline is None and actor.claim_deadline is None
        paused_event = sockets[other].last("event.paused")
        assert paused_event is not None
        assert paused_event["data"]["paused"] is True

        snapshot = sockets[other].last("state.snapshot")
        assert snapshot["data"]["paused"]["paused"] is True

        # 暂停期间不接受出牌
        turnSeat = actor.engine.turn
        current = next(
            slot.login_id for slot in actor.slots if slot is not None and slot.seat == turnSeat
        )
        tile = next(index for index, count in enumerate(actor.engine.seats[turnSeat].counts) if count)
        before = len([m for m in sockets[current].messages if m["type"] == "error"])
        await actor.handle(current, {"type": "game.action", "data": {"action": "discard", "tiles": [tile]}})
        error = sockets[current].last("error")
        assert error is not None and error["data"]["code"] == "ROOM_PAUSED"
        assert len([m for m in sockets[current].messages if m["type"] == "error"]) == before + 1

        await actor.handle(other, {"type": "room.resume", "data": {}})
        assert actor.paused is False
        assert actor.paused_by_seat is None
        resumed = sockets[owner].last("event.paused")
        assert resumed["data"]["paused"] is False
    finally:
        actor._clear_timers()


async def test_pause_rejected_for_family_without_switch(s5_env):
    """通用族没有 pause 开关（capability.switches 里没有），直接拒绝。"""
    from test_ws_flow import build_actor

    actor, sockets = build_actor(s5_env)
    owner = s5_env["owner"]
    try:
        for loginID in s5_env["members"]:
            await actor.handle(loginID, {"type": "seat.ready", "data": {}})
        await actor.handle(owner, {"type": "game.start", "data": {}})
        await actor.handle(owner, {"type": "room.pause", "data": {}})
        error = sockets[owner].last("error")
        assert error is not None and error["data"]["code"] == "PAUSE_UNSUPPORTED"
        assert actor.paused is False
    finally:
        actor._clear_timers()


# ---------------------------------------------------------------- 13.13 落库


def _round_row(gameID: int) -> dict:
    from common import mysqlCommon

    rows = mysqlCommon.queryTableGeneral(
        mysqlCommon.MJ_GAME_ROUND_TABLE,
        condList=[["gameID", "=", gameID]],
        order="`recID` desc",
        limitNum=1,
    )
    return rows[0] if rows else {}


def test_case13_round_persisted_with_fan_raw_and_payer(s5_env, hand):
    from common import miscCommon as misc
    from common import mysqlCommon
    from realtime import persist

    familyID = s5_env["family_id"]
    now = misc.getTime()
    gameID = mysqlCommon.insert_mj_game(
        mysqlCommon.MJ_GAME_TABLE,
        {
            "familyID": familyID,
            "roomID": s5_env["room"]["id"],
            "ruleFamilyCode": "baishi",
            "ruleSnapshot": {"rule_family_code": "baishi"},
            "gameStatus": "PLAYING",
            "startedYMDHMS": now,
            "regYMDHMS": now,
            "delFlag": "0",
        },
    )
    assert gameID > 0
    for seat in range(4):
        mysqlCommon.insert_mj_game_player(
            mysqlCommon.MJ_GAME_PLAYER_TABLE,
            {
                "gameSeatKey": f"{gameID}_{seat}",
                "gameID": gameID,
                "familyID": familyID,
                "seatNo": seat,
                "loginID": f"13900000{seat:03d}",
                "displayName": f"柏{seat}",
                "totalScore": 0,
                "regID": "pytest",
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )

    eng = prepare(engine(dealer_seat=0), hand, {1: "777m44m"}, turn=1)
    eng.seats[1].melds = [pong(0), pong(2), pong(4)]
    eng.seats[1].counts = counts_from_tiles(hand("777m44m"))
    ctx = eng._ctx(1, win_tile=6, is_self_draw=False, extra_tile=None)
    breakdown = _eval(ctx)
    assert breakdown.fan_total == 40
    eng._finish_win(1, "discard", 6, breakdown, 2, ctx)
    settled = eng.result
    assert settled is not None

    payload = settled
    try:
        persist.save_round(gameID, familyID, payload)
        row = _round_row(gameID)
        assert row, "结算应落库"
        assert int(row.get("fanRaw") or 0) == int(row.get("fanTotal") or 0) == 40
        assert row.get("winType") == "discard"
        payer = row.get("payerJson")
        assert isinstance(payer, list) and payer, "包牌付款方可还原"
        assert payer[0]["reason"] == "bao_pai"
        assert payer[0]["bao_pai_seat"] == 2
        assert payer[0]["amount"] == 160
    finally:
        mysqlCommon.updateTableGeneral(
            mysqlCommon.MJ_GAME_TABLE,
            "recID = %s",
            [gameID],
            {"gameStatus": "FINISHED", "endedYMDHMS": misc.getTime(), "delFlag": "1"},
        )
