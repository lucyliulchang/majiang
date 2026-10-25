"""三组「开关 + 从属配置」的行为：关闭时既不校验也不取用，但保留原值。"""

import pytest
from pydantic import ValidationError

from app.game.scoring import kong_delta
from app.schemas.rule import (
    KongScore,
    PatternSwitches,
    RuleConfig,
    ThirteenUnrelatedOptions,
    ToggleValue,
    TurnTimeout,
)


def test_turn_timeout_enabled_validates_range():
    with pytest.raises(ValidationError):
        RuleConfig(turn_timeout=TurnTimeout(enabled=True, seconds=5))


def test_turn_timeout_disabled_skips_validation():
    rule = RuleConfig(turn_timeout=TurnTimeout(enabled=False, seconds=5))
    assert rule.turn_timeout.enabled is False
    assert rule.brief()["turn_timeout"]["seconds"] is None


def test_turn_timeout_enabled_reports_seconds():
    rule = RuleConfig(turn_timeout=TurnTimeout(enabled=True, seconds=30))
    assert rule.brief()["turn_timeout"]["seconds"] == 30


def test_kong_score_enabled_validates_range():
    with pytest.raises(ValidationError):
        RuleConfig(kong_score=KongScore(enabled=True, exposed=99))


def test_kong_score_disabled_ignores_dirty_values():
    rule = RuleConfig(kong_score=KongScore(enabled=False, exposed=99, hidden=99, added=99))
    assert rule.kong_points("exposed") == 0
    assert rule.brief()["kong_score"]["exposed"] == 0


def test_kong_delta_zero_when_disabled():
    rule = RuleConfig(kong_score=KongScore(enabled=False, exposed=5, hidden=5, added=5))
    assert kong_delta(rule, 1, "exposed", 0) == [0, 0, 0, 0]
    assert kong_delta(rule, 1, "hidden") == [0, 0, 0, 0]


def test_kong_delta_when_enabled():
    rule = RuleConfig(kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1))
    # 明杠：放杠的那位付
    assert kong_delta(rule, 1, "exposed", 0) == [-1, 1, 0, 0]
    # 暗杠：三家各付
    assert kong_delta(rule, 1, "hidden") == [-2, 6, -2, -2]


def test_ting_hint_brief():
    assert RuleConfig(ting_hint=ToggleValue(enabled=False)).brief()["ting_hint"] is False
    assert RuleConfig(ting_hint=ToggleValue(enabled=True)).brief()["ting_hint"] is True


def test_at_least_one_pattern_required():
    with pytest.raises(ValidationError):
        RuleConfig(
            patterns=PatternSwitches(
                standard=False,
                seven_pairs=False,
                thirteen_orphans=False,
                thirteen_unrelated=ThirteenUnrelatedOptions(enabled=False),
            )
        )


def test_duplicate_fan_ids_rejected():
    base = RuleConfig()
    duplicated = [base.fan_table[0].model_copy(), base.fan_table[0].model_copy()]
    with pytest.raises(ValidationError):
        RuleConfig(fan_table=duplicated)


def test_empty_fan_table_rejected():
    with pytest.raises(ValidationError):
        RuleConfig(fan_table=[])


def test_draw_penalty_switch():
    rule = RuleConfig(draw_penalty=ToggleValue(enabled=True, value=3))
    assert rule.draw_penalty.enabled is True
    disabled = RuleConfig(draw_penalty=ToggleValue(enabled=False, value=99))
    assert disabled.draw_penalty.value == 99
