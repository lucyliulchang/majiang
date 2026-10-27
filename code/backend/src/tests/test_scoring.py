from game.fan import evaluate
from game.patterns.base import FanHit, WinResult
from game.scoring import settle_draw, settle_rob_kong, settle_win
from schemas.rule import KongScore, RuleConfig, ToggleValue


def test_self_draw_all_pay():
    rule = RuleConfig(fan_mode="linear", fan_cap=None, base_score=10)
    bd = evaluate(WinResult("standard", "标准胡", [FanHit("zi_mo", 1)]), rule)
    outcome = settle_win(rule, winner_seat=2, breakdown=bd, is_self_draw=True, discard_seat=None)
    assert outcome.win_type == "self_draw"
    assert outcome.delta[2] == bd.score * 3
    assert outcome.delta[0] == -bd.score


def test_discard_single_payer():
    rule = RuleConfig(
        fan_mode="linear", fan_cap=None, base_score=10, discard_pay_mode="single"
    )
    bd = evaluate(WinResult("standard", "标准胡", [FanHit("zi_mo", 1)]), rule)
    outcome = settle_win(rule, winner_seat=2, breakdown=bd, is_self_draw=False, discard_seat=3)
    assert outcome.delta[3] == -bd.score
    assert outcome.delta[0] == 0
    assert outcome.delta[2] == bd.score


def test_discard_pay_all_mode():
    rule = RuleConfig(
        fan_mode="linear", fan_cap=None, base_score=10, discard_pay_mode="all"
    )
    bd = evaluate(WinResult("standard", "标准胡", [FanHit("zi_mo", 1)]), rule)
    outcome = settle_win(rule, winner_seat=2, breakdown=bd, is_self_draw=False, discard_seat=3)
    assert outcome.delta[0] == -bd.score
    assert outcome.delta[1] == -bd.score
    assert outcome.delta[3] == -bd.score
    assert outcome.delta[2] == bd.score * 3


def test_kong_points_carried_into_round():
    rule = RuleConfig(fan_mode="linear", fan_cap=None, base_score=10)
    bd = evaluate(WinResult("standard", "标准胡", [FanHit("zi_mo", 1)]), rule)
    outcome = settle_win(
        rule,
        winner_seat=0,
        breakdown=bd,
        is_self_draw=True,
        discard_seat=None,
        kong_accumulated=[-3, 1, 1, 1],
    )
    assert outcome.delta[0] == bd.score * 3 - 3
    assert outcome.delta[1] == -bd.score + 1


def test_draw_no_penalty_by_default():
    rule = RuleConfig()
    outcome = settle_draw(rule, dealer_seat=0)
    assert outcome.win_type == "none"
    assert outcome.delta == [0, 0, 0, 0]


def test_draw_penalty_pays_dealer():
    rule = RuleConfig(draw_penalty=ToggleValue(enabled=True, value=3))
    outcome = settle_draw(rule, dealer_seat=1)
    assert outcome.delta == [-3, 9, -3, -3]


def test_kong_disabled_never_pays():
    rule = RuleConfig(kong_score=KongScore(enabled=False, exposed=9, hidden=9, added=9))
    outcome = settle_draw(rule, dealer_seat=0, kong_accumulated=[0, 0, 0, 0])
    assert outcome.delta == [0, 0, 0, 0]


def test_rob_kong_pays_by_kong_player():
    rule = RuleConfig(fan_mode="linear", fan_cap=None, base_score=10)
    bd = evaluate(WinResult("standard", "标准胡", [FanHit("qiang_gang_hu", 1)]), rule)
    outcome = settle_rob_kong(rule, winner_seat=1, breakdown=bd, kong_seat=2)
    assert outcome.delta[2] == -bd.score
    assert outcome.delta[1] == bd.score
