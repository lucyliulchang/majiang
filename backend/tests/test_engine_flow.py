"""对局状态机：发牌、摸打、仲裁优先级、杠分开关、抢杠胡、荒庄。"""

from app.game.engine import EngineError
from app.game.hand import Meld
from app.game.tiles import counts_from_tiles
from app.schemas.rule import KongScore, RuleConfig


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


def test_wall_exhausted_settles_as_draw(engine_factory, hand):
    engine = prepare(engine_factory(), hand, {0: "5m1p2p3p4p5p6p7p8p9p1s2s3s4s", 1: "", 2: "", 3: ""})
    engine.front = engine.back + 1
    assert engine.remaining == 0
    engine.apply_action(0, {"action": "discard", "tiles": [4]})
    assert engine.phase == "settled"
    assert engine.result is not None
    assert engine.result.win_type == "none"


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
