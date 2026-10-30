"""对局状态机：发牌、摸打、仲裁优先级、杠分开关、抢杠胡、荒庄。"""

import pytest

from game.claims import chow_options
from game.engine import EngineError
from game.hand import Meld
from game.tiles import counts_from_tiles
from game.families.generic.config import KongScore, RuleConfig


def prepare(engine, hand, mapping: dict[int, str], turn: int = 0):
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


def test_start_round_deals_correctly(engine_factory):
    engine = engine_factory()
    engine.start_round()
    assert sum(engine.seats[0].counts) == 14  # 庄家 14 张
    for seat in (1, 2, 3):
        assert sum(engine.seats[seat].counts) == 13
    assert engine.remaining == 136 - 53
    assert engine.phase == "discard"
    assert engine.turn == 0


def test_discard_moves_tile_to_river(engine_factory, hand):
    engine = prepare(engine_factory(), hand, {0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s"})
    tile = 4  # 五万
    engine.apply_action(0, {"action": "discard", "tiles": [tile]})
    assert tile in engine.seats[0].discards
    assert engine.seats[0].counts[tile] == 0


def test_discard_rejects_tile_not_in_hand(engine_factory, hand):
    engine = prepare(engine_factory(), hand, {0: "1m"})
    try:
        engine.apply_action(0, {"action": "discard", "tiles": [5]})
        raise AssertionError("应当拒绝出不在手里的牌")
    except EngineError as error:
        assert error.code == "NOT_IN_HAND"


def test_not_your_turn_rejected(engine_factory, hand):
    engine = prepare(engine_factory(), hand, {0: "1m", 1: "2m"})
    try:
        engine.apply_action(1, {"action": "discard", "tiles": [1]})
        raise AssertionError("应当拒绝非当前玩家的操作")
    except EngineError as error:
        assert error.code == "NOT_YOUR_TURN"


def test_pong_beats_chow(engine_factory, hand):
    engine = prepare(
        engine_factory(),
        hand,
        {
            0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s",
            1: "4m6m",  # 四万 + 六万，可吃五万
            2: "5m5m",  # 可碰五万
            3: "",
        },
    )
    events = engine.apply_action(0, {"action": "discard", "tiles": [4]})
    assert any(event["type"] == "event.claim_open" for event in events)
    assert engine.phase == "claim"

    engine.apply_action(1, {"action": "chow", "tiles": [3, 5]})
    assert engine.phase == "claim"  # 还在等座位 2

    engine.apply_action(2, {"action": "pong"})
    assert engine.phase == "discard"
    assert engine.turn == 2
    melds = engine.seats[2].melds
    assert melds and melds[0].kind == "pong"
    assert melds[0].tiles == [4, 4, 4]


def test_hu_beats_pong(engine_factory, hand):
    engine = prepare(
        engine_factory(),
        hand,
        {
            0: "1s1p2p3p4p5p6p7p8p9p1m2m3m4m",
            1: "1s1s",  # 可碰一条
            2: "123m456m789m123p1s",  # 听一条，可胡
            3: "",
        },
    )
    engine.apply_action(0, {"action": "discard", "tiles": [18]})
    engine.apply_action(1, {"action": "pong"})
    engine.apply_action(2, {"action": "hu"})
    assert engine.phase == "settled"
    assert engine.result is not None
    assert engine.result.winner_seat == 2
    assert engine.result.win_type == "discard"


def test_pass_returns_turn_to_next_seat(engine_factory, hand):
    engine = prepare(
        engine_factory(),
        hand,
        {0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s", 1: "5m5m", 2: "", 3: ""},
    )
    engine.apply_action(0, {"action": "discard", "tiles": [4]})
    engine.apply_action(1, {"action": "pass"})
    assert engine.phase == "discard"
    assert engine.turn == 1
    assert sum(engine.seats[1].counts) == 3  # 碰的两张 + 摸一张


def test_claim_timeout_treats_as_pass(engine_factory, hand):
    engine = prepare(
        engine_factory(),
        hand,
        {0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s", 1: "5m5m", 2: "", 3: ""},
    )
    engine.apply_action(0, {"action": "discard", "tiles": [4]})
    events = engine.timeout_claim()
    assert engine.phase == "discard"
    assert engine.turn == 1
    assert any(event["type"] == "event.drawn" for event in events)


def test_hidden_kong_awards_points_when_enabled(engine_factory, hand):
    rule = RuleConfig(kong_score=KongScore(enabled=True, hidden=2))
    engine = prepare(engine_factory(rule), hand, {0: "1m1m1m1m2p3p4p5p6p7p8p1s2s3s"})
    engine.apply_action(0, {"action": "kong", "kong_kind": "hidden", "tiles": [0]})
    assert engine.seats[0].melds[0].kind == "kong_hidden"
    assert engine.seats[0].round_score == 6


def test_hidden_kong_allowed_but_scores_nothing_when_disabled(engine_factory, hand):
    rule = RuleConfig(kong_score=KongScore(enabled=False, hidden=2))
    engine = prepare(engine_factory(rule), hand, {0: "1m1m1m1m2p3p4p5p6p7p8p1s2s3s"})
    events = engine.apply_action(0, {"action": "kong", "kong_kind": "hidden", "tiles": [0]})
    assert engine.seats[0].melds and engine.seats[0].melds[0].kind == "kong_hidden"
    assert not any(event["type"] == "event.kong_score" for event in events)
    assert engine.seats[0].round_score == 0


def test_wall_exhausted_without_kong_restarts_same_round(engine_factory, hand):
    """荒庄二分 · 无杠：本局作废不落库，局号/庄家/局风不变，广播 round_restarted（03 §3.6）。"""
    engine = prepare(engine_factory(), hand, {0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s", 1: "", 2: "", 3: ""})
    engine.front = engine.back + 1
    assert engine.remaining == 0
    events = engine.apply_action(0, {"action": "discard", "tiles": [4]})
    restarted = [event for event in events if event["type"] == "event.round_restarted"]
    assert restarted, "无杠荒庄必须走重发分支"
    assert restarted[0]["data"]["reason"] == "no_kong"
    assert restarted[0]["data"]["round_no"] == 1
    assert restarted[0]["data"]["dealer_seat"] == 0
    assert restarted[0]["data"]["round_wind"] == 0
    # 重发后回到出牌阶段，不产生结算结果
    assert engine.phase == "discard"
    assert engine.result is None
    assert engine.restarts == 1
    assert engine.round_no == 1
    assert engine.dealer_seat == 0
    assert engine.round_wind == 0
    # 重新发牌：庄家 14、闲家各 13
    assert sum(engine.seats[0].counts) == 14
    assert [sum(engine.seats[seat].counts) for seat in (1, 2, 3)] == [13, 13, 13]


def test_wall_exhausted_with_kong_settles_as_draw(engine_factory, hand):
    """荒庄二分 · 有杠：记荒庄、杠分保留、局号+1 由上层推进、庄家迁下家（03 §3.6）。"""
    rule = RuleConfig(kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1))
    engine = prepare(
        engine_factory(rule), hand, {0: "1m1m1m1m2p3p4p5p6p7p8p1s2s3s", 1: "", 2: "", 3: ""}
    )
    engine.apply_action(0, {"action": "kong", "kong_kind": "hidden", "tiles": [0]})
    assert engine.kong_happened is True

    engine.front = engine.back + 1
    assert engine.remaining == 0
    engine.apply_action(0, {"action": "discard", "tiles": [16]})
    assert engine.phase == "settled"
    assert engine.result is not None
    assert engine.result.winner_seat is None
    assert engine.result.win_type == "none"
    assert engine.result.is_draw is True
    # 杠分已即时结算，荒庄不回滚、不罚分
    assert engine.result.score_delta == [6, -2, -2, -2]
    assert sum(engine.result.score_delta) == 0
    assert engine.result.kong_delta == [6, -2, -2, -2]
    # 迁庄：北位下庄即圈结束
    assert engine.next_dealer() == 1


def test_rob_kong_window_opens_and_settles(engine_factory, hand):
    engine = prepare(
        engine_factory(),
        hand,
        {
            0: "",
            1: "7m",
            2: "123p456p789p99s5m6m",
            3: "",
        },
        turn=1,
    )
    engine.seats[1].melds = [Meld(kind="pong", tiles=[6, 6, 6], from_seat=0)]
    events = engine.apply_action(1, {"action": "kong", "kong_kind": "added", "tiles": [6]})
    assert any(
        event["type"] == "event.claim_open" and event["data"]["reason"] == "rob_kong"
        for event in events
    )
    assert engine.phase == "claim"

    engine.apply_action(2, {"action": "hu"})
    assert engine.phase == "settled"
    assert engine.result is not None
    assert engine.result.winner_seat == 2
    assert engine.result.score_delta[1] < 0


def test_rob_kong_passed_then_kong_applies(engine_factory, hand):
    engine = prepare(
        engine_factory(),
        hand,
        {0: "", 1: "7m", 2: "123p456p789p99s5m6m", 3: ""},
        turn=1,
    )
    engine.seats[1].melds = [Meld(kind="pong", tiles=[6, 6, 6], from_seat=0)]
    engine.apply_action(1, {"action": "kong", "kong_kind": "added", "tiles": [6]})
    engine.apply_action(2, {"action": "pass"})
    assert engine.phase == "discard"
    assert engine.seats[1].melds[0].kind == "kong_added"


def test_dealer_keeps_turn_on_win(engine_factory, hand):
    engine = prepare(
        engine_factory(),
        hand,
        {0: "1s1p2p3p4p5p6p7p8p9p1m2m3m4m", 2: "123m456m789m123p1s", 1: "", 3: ""},
    )
    engine.apply_action(0, {"action": "discard", "tiles": [18]})
    engine.apply_action(2, {"action": "hu"})
    assert engine.result is not None
    assert engine.next_dealer() == 1  # 庄家没胡，下家坐庄


# ---------------------------------------------------------------- v1.1.0 U-1 胡牌优先 / 过胡
# 座位 1 手牌 55m123m789m123p99p：五万既能让它胡（555m + 三面子 + 99p 将），
# 又能碰（手里本来就两张五万）→ 这正是"先只问胡"的标准场景。
HU_PONG_HANDS = {
    0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s",
    1: "55m123m789m123p99p",
    2: "",
    3: "",
}


def _open_hu_pong_window(engine_factory, hand):
    engine = prepare(engine_factory(), hand, dict(HU_PONG_HANDS))
    events = engine.apply_action(0, {"action": "discard", "tiles": [4]})
    assert any(event["type"] == "event.claim_open" for event in events)
    assert engine.phase == "claim"
    return engine


def _actions(engine, seat: int) -> list[str]:
    return [option["action"] for option in engine.legal_actions(seat)["actions"]]


def test_hu_stage_only_offers_hu_and_pass(engine_factory, hand):
    """可胡可碰：窗口内部算全，但快照只下发 hu/pass（吃碰先藏起来）。"""
    engine = _open_hu_pong_window(engine_factory, hand)
    window = engine.claim
    assert window is not None
    # 服务端一次算全：吃碰选项仍在窗口里，过滤只发生在 available()
    assert [option["action"] for option in window.options[1]] == ["hu", "pong"]
    legal = engine.legal_actions(1)
    assert [option["action"] for option in legal["actions"]] == ["hu", "pass"]
    assert legal["claim_tile"] == 4 and legal["claim_from"] == 0
    assert window.pending() == [1], "还没给终态，窗口不能算问完"


def test_hu_stage_pass_reveals_pong_and_pong_works(engine_factory, hand):
    """过胡之后同一窗口补发碰（无 hu），碰照常成立。"""
    engine = _open_hu_pong_window(engine_factory, hand)
    assert engine.apply_action(1, {"action": "pass"}) == []
    assert engine.phase == "claim", "过胡只是本窗口的一段，不能关窗"
    assert 1 in engine.claim.passed_hu
    assert _actions(engine, 1) == ["pong", "pass"]

    engine.apply_action(1, {"action": "pong", "tiles": [4]})
    assert engine.phase == "discard" and engine.turn == 1
    assert engine.claim is None
    melds = engine.seats[1].melds
    assert melds and melds[0].kind == "pong" and melds[0].tiles == [4, 4, 4]


def test_hu_stage_rejects_pong_without_eating_hu(engine_factory, hand):
    """胡阶段直接构造 pong → BAD_ACTION，且胡还在（不会被静默吃掉）。"""
    engine = _open_hu_pong_window(engine_factory, hand)
    with pytest.raises(EngineError) as caught:
        engine.apply_action(1, {"action": "pong", "tiles": [4]})
    assert caught.value.code == "BAD_ACTION"
    assert engine.claim is not None and engine.claim.responses == {}
    assert _actions(engine, 1) == ["hu", "pass"]
    assert sum(engine.seats[1].counts) == 13, "被拒的动作不得改手牌"


def test_hu_stage_pass_then_timeout_closes_window(engine_factory, hand):
    """过胡后不再操作 → 超时按终态 pass 收窗，牌局继续（不会卡死）。"""
    engine = _open_hu_pong_window(engine_factory, hand)
    engine.apply_action(1, {"action": "pass"})
    assert engine.claim is not None and engine.claim.available(1)[-1]["action"] == "pass"

    events = engine.timeout_claim()
    assert events, "超时必须推进牌局"
    assert engine.claim is None
    assert engine.phase == "discard" and engine.turn == 1


def test_hu_comes_back_on_next_tile(engine_factory, hand):
    """过胡只对当前这张牌生效：同一张牌再打一次，hu 重新出现。"""
    engine = _open_hu_pong_window(engine_factory, hand)
    engine.apply_action(1, {"action": "pass"})  # 过胡
    engine.apply_action(1, {"action": "pass"})  # 第二阶段彻底放弃
    assert engine.claim is None and engine.phase == "discard"

    # 复位成"座位 0 再打一张五万"：全新窗口，passed_hu 不跨窗口
    engine.seats[0].counts[4] += 1
    engine.seats[1].counts = counts_from_tiles(hand(HU_PONG_HANDS[1]))
    engine.seats[1].melds = []
    engine.turn = 0
    engine.phase = "discard"
    engine.last_draw = None
    engine.apply_action(0, {"action": "discard", "tiles": [4]})
    assert engine.claim is not None and engine.claim.passed_hu == set()
    assert _actions(engine, 1) == ["hu", "pass"]


# ---------------------------------------------------------------- 胡即收口（短路仲裁）
# 座位 1 能吃五万（4m6m），座位 2 听五万（3m4m 搭子）——去掉牌局里"胡了还要等别人点过"的空等。
CHOW_HU_HANDS = {
    0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s",
    1: "46m1p2p3p4p5p6p7p8p9p1s2s",  # 只有吃，胡不了
    2: "34m123m789m123p11p",  # 只有胡，手里没五万碰不了
    3: "",
}


def test_hu_settles_immediately_when_no_one_else_can_hu(engine_factory, hand):
    """1 号能吃、2 号能胡：2 号点胡立刻结算，不必等 1 号点吃/过。"""
    engine = prepare(engine_factory(), hand, dict(CHOW_HU_HANDS))
    engine.apply_action(0, {"action": "discard", "tiles": [4]})
    window = engine.claim
    assert window is not None and 1 in window.options and 2 in window.options
    assert [option["action"] for option in window.options[1]] == ["chow"]
    assert _actions(engine, 2) == ["hu", "pass"]

    engine.apply_action(2, {"action": "hu"})
    assert engine.phase == "settled", "没有别人能胡时，胡必须立即收口"
    assert engine.result is not None and engine.result.winner_seat == 2
    assert engine.result.win_type == "discard"
    # 吃家迟到的提交只能是"本局已结束"，不会被当成吃生效
    with pytest.raises(EngineError) as caught:
        engine.apply_action(1, {"action": "chow", "tiles": [3, 5]})
    assert caught.value.code == "ROUND_OVER"
    assert engine.seats[1].melds == []


def test_hu_waits_when_another_seat_can_also_hu(engine_factory, hand):
    """两家都能胡：先点胡的不许抢跑，仍要等齐后按下家优先仲裁。"""
    engine = prepare(
        engine_factory(),
        hand,
        {
            0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s",
            1: "34m123m789m123p11p",  # 听五万（又是下家，仲裁时优先）
            2: "67m123m789m123p11p",  # 也听五万，但离打牌者更远
            3: "",
        },
    )
    engine.apply_action(0, {"action": "discard", "tiles": [4]})
    engine.apply_action(2, {"action": "hu"})  # 手快先点
    assert engine.phase == "claim", "还有别人能胡，不能短路"
    assert engine.result is None

    engine.apply_action(1, {"action": "hu"})
    assert engine.phase == "settled"
    assert engine.result is not None and engine.result.winner_seat == 1, "同优先级下家优先"


# ---------------------------------------------------------------- v1.1.0 U-2 吃牌选两张
# 座位 1 手牌 `234556 万`：来 4 万时被吃牌可作顺子的低 / 中 / 高张，
# 因此 234 / 345 / 456 三组都能成副露（改进文档 U-2 的核心用例）。
CHOW_PICK_HANDS = {
    0: "4m1p2p3p4p5p6p7p8p9p1s2s3s4s",
    1: "234556m1p2p3p4p5p6p",
    2: "",
    3: "",
}
# 万 0–8：1m=0 … 9m=8；4 万 = 3
DISCARD_4M = 3


def _open_chow_window(engine_factory, hand, seat1: str):
    """摆成「座位 0 打出四万，座位 1 手里有 seat1」的吃牌窗口。"""
    engine = prepare(engine_factory(), hand, {**CHOW_PICK_HANDS, 1: seat1})
    engine.apply_action(0, {"action": "discard", "tiles": [DISCARD_4M]})
    assert engine.phase == "claim" and engine.claim is not None
    assert 1 in engine.claim.options
    return engine


def test_chow_options_enumerates_low_mid_high(hand):
    """组合枚举覆盖"被吃牌作低/中/高张"三态，旧实现只算得出居中那一组。"""
    counts = counts_from_tiles(hand("234556m"))
    # 2万3万（234）/ 3万5万（345）/ 5万6万（456）
    assert chow_options(counts, DISCARD_4M, True) == [[1, 2], [2, 4], [4, 5]]
    # 手里没有 6 万 → 456 那组被"可用性"过滤掉
    assert chow_options(counts_from_tiles(hand("23455m")), DISCARD_4M, True) == [[1, 2], [2, 4]]
    # 关掉吃 / 字牌：不给组合
    assert chow_options(counts, DISCARD_4M, False) == []
    assert chow_options(counts, 27, True) == []


@pytest.mark.parametrize("partners", [[1, 2], [2, 4], [4, 5]])
def test_chow_any_of_three_combos_becomes_meld(engine_factory, hand, partners):
    """三组候选任选其一都能成副露，`Meld.tiles` 就是对应的三张顺子。"""
    engine = _open_chow_window(engine_factory, hand, CHOW_PICK_HANDS[1])
    before = list(engine.seats[1].counts)

    engine.apply_action(1, {"action": "chow", "tiles": partners})

    assert engine.phase == "discard" and engine.turn == 1
    meld = engine.seats[1].melds[-1]
    assert meld.kind == "chow"
    assert meld.from_seat == 0 and meld.claim_tile == DISCARD_4M
    assert meld.tiles == sorted([DISCARD_4M, *partners])
    assert [meld.tiles[1] - meld.tiles[0], meld.tiles[2] - meld.tiles[1]] == [1, 1], "必须是顺子"
    # 手牌各扣一张，打出去的四万被从牌河取走
    for partner in partners:
        assert engine.seats[1].counts[partner] == before[partner] - 1
    assert engine.seats[1].counts[DISCARD_4M] == before[DISCARD_4M]
    assert DISCARD_4M not in engine.seats[0].discards


def test_chow_rejects_non_consecutive_pair(engine_factory, hand):
    """2 万 + 6 万 不成顺：BAD_CHOW，窗口保持打开、手牌不动，可改选合法组合。"""
    engine = _open_chow_window(engine_factory, hand, CHOW_PICK_HANDS[1])
    before = list(engine.seats[1].counts)

    with pytest.raises(EngineError) as caught:
        engine.apply_action(1, {"action": "chow", "tiles": [1, 5]})
    assert caught.value.code == "BAD_CHOW"
    assert caught.value.message == "吃牌的两张必须与被吃的牌组成顺子"
    assert engine.phase == "claim" and engine.claim is not None
    assert engine.claim.responses == {}, "被拒的动作不得入 responses"
    assert engine.seats[1].counts == before and engine.seats[1].melds == []

    engine.apply_action(1, {"action": "chow", "tiles": [2, 4]})
    assert engine.seats[1].melds[-1].tiles == [2, 3, 4]


def test_chow_rejects_cross_suit_pair(engine_factory, hand):
    """3 万 + 5 筒 跨越花色：牌面连续也不算顺子。"""
    engine = _open_chow_window(engine_factory, hand, CHOW_PICK_HANDS[1])
    with pytest.raises(EngineError) as caught:
        engine.apply_action(1, {"action": "chow", "tiles": [2, 13]})
    assert caught.value.code == "BAD_CHOW"
    assert engine.claim is not None and engine.claim.responses == {}
    assert engine.seats[1].melds == []


def test_chow_rejects_pair_missing_in_hand(engine_factory, hand):
    """手里凑不齐这两张（差一张 / 差一种）：BAD_CHOW。"""
    # 23455 万 + 1–8 筒：有 5 万、没有 6 万 → 456 那组凑不齐
    engine = _open_chow_window(engine_factory, hand, "23455m1p2p3p4p5p6p7p8p")
    with pytest.raises(EngineError) as caught:
        engine.apply_action(1, {"action": "chow", "tiles": [4, 5]})
    assert caught.value.code == "BAD_CHOW"
    assert engine.claim is not None and engine.claim.responses == {}

    # 完全不在手里的 1 万 → 同样拒绝
    engine = _open_chow_window(engine_factory, hand, CHOW_PICK_HANDS[1])
    with pytest.raises(EngineError) as caught:
        engine.apply_action(1, {"action": "chow", "tiles": [0, 1]})
    assert caught.value.code == "BAD_CHOW"


def test_chow_pass_keeps_game_going(engine_factory, hand):
    """选牌态「过」= 正常 pass：窗口关闭、下家摸牌，副露不产生。"""
    engine = _open_chow_window(engine_factory, hand, CHOW_PICK_HANDS[1])
    engine.apply_action(1, {"action": "pass"})
    assert engine.claim is None and engine.phase == "discard"
    assert engine.turn == 1
    assert engine.seats[1].melds == []
    assert engine.seats[0].discards == [DISCARD_4M], "过掉的牌留在牌河里"
