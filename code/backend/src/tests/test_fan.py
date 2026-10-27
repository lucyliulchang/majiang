from app.game.fan import best_win, evaluate, score_from_fan
from app.game.patterns.base import FanHit, WinResult
from app.schemas.rule import RuleConfig


def make_win(*hits: tuple[str, int]) -> WinResult:
    return WinResult(
        pattern_id="standard",
        pattern_name="标准胡",
        fan_hits=[FanHit(fid, count) for fid, count in hits],
    )


def test_exponential_and_linear_modes():
    exponential = RuleConfig(fan_mode="exponential", fan_cap=None, base_score=1)
    linear = RuleConfig(fan_mode="linear", fan_cap=None, base_score=1)
    assert score_from_fan(3, exponential) == 8
    assert score_from_fan(3, linear) == 3
    assert score_from_fan(0, exponential) == 1
    assert score_from_fan(0, linear) == 1


def test_base_score_multiplier():
    rule = RuleConfig(fan_mode="exponential", fan_cap=None, base_score=2)
    assert score_from_fan(3, rule) == 16


def test_fan_cap_applied():
    rule = RuleConfig(fan_cap=2, fan_mode="exponential", base_score=1)
    breakdown = evaluate(make_win(("qing_yi_se", 1), ("zi_mo", 1)), rule)
    assert breakdown.fan_raw == 7
    assert breakdown.fan_total == 2
    assert breakdown.capped is True
    assert breakdown.score == 4


def test_exclusive_group_keeps_highest():
    rule = RuleConfig(fan_cap=None)
    breakdown = evaluate(make_win(("qing_yi_se", 1), ("hun_yi_se", 1)), rule)
    names = {line.id for line in breakdown.lines}
    assert "qing_yi_se" in names
    assert "hun_yi_se" not in names


def test_stackable_kong_counts_multiple():
    rule = RuleConfig(fan_cap=None)
    breakdown = evaluate(make_win(("kong", 3), ("zi_mo", 1)), rule)
    kong_line = next(line for line in breakdown.lines if line.id == "kong")
    assert kong_line.count == 3
    assert breakdown.fan_raw == 3 + 1


def test_non_stackable_repeats_collapse():
    rule = RuleConfig(fan_cap=None)
    breakdown = evaluate(make_win(("zi_mo", 5),), rule)
    line = next(line for line in breakdown.lines if line.id == "zi_mo")
    assert line.count == 1


def test_unknown_fan_id_is_ignored():
    rule = RuleConfig(fan_cap=None)
    breakdown = evaluate(make_win(("no_such_fan", 1), ("zi_mo", 1)), rule)
    assert [line.id for line in breakdown.lines] == ["zi_mo"]


def test_best_win_picks_highest_score():
    rule = RuleConfig(fan_cap=None)
    small = WinResult("standard", "标准胡", [FanHit("ping_hu", 1)])
    big = WinResult("seven_pairs", "七对", [FanHit("qi_dui", 1)])
    assert best_win([small, big], rule).pattern_id == "seven_pairs"


def test_best_win_empty():
    assert best_win([], RuleConfig()) is None
