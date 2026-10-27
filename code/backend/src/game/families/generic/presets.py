"""通用族 4 套预置模板（03 §4.5）。

与 S6 之前的 `tools/seedPresets.py` 逐字段一致（对比脚本 `tools/comparePresets.py`）：
`generic_standard` / `generic_no_chow` / `generic_unrelated` / `generic_casual`。

config 一律走 `RuleConfig` 强校验后再 dump，避免种子写坏数据；
`dealer_continue_on_win/draw` 已随模型移除，不再出现在任何模板里。
"""

from __future__ import annotations

from game.families.generic.config import (
    KongScore,
    PatternSwitches,
    RuleConfig,
    ThirteenUnrelatedOptions,
    ToggleValue,
    TurnTimeout,
)
from game.families.registry import PresetTemplate


def _config(**overrides) -> dict:
    """生成模板 config：以 RuleConfig 默认为基，只覆盖差异项。"""
    return RuleConfig(**overrides).model_dump()


def preset_configs() -> dict[str, dict]:
    """templateCode → config；`tools/comparePresets.py` 也用它做逐字段对比。"""
    standard = _config(
        base_score=1,
        fan_mode="exponential",
        fan_cap=8,
        allow_chow=True,
        turn_timeout=TurnTimeout(enabled=True, seconds=15),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    no_chow = _config(
        base_score=1,
        fan_mode="linear",
        fan_cap=12,
        allow_chow=False,
        turn_timeout=TurnTimeout(enabled=True, seconds=20),
        kong_score=KongScore(enabled=True, exposed=2, hidden=4, added=2),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    with_unrelated = _config(
        base_score=1,
        fan_mode="exponential",
        fan_cap=10,
        allow_chow=True,
        patterns=PatternSwitches(
            standard=True,
            seven_pairs=True,
            thirteen_orphans=True,
            thirteen_unrelated=ThirteenUnrelatedOptions(
                enabled=True, require_all_honors=False, allow_pair=True, min_gap=3
            ),
        ),
        turn_timeout=TurnTimeout(enabled=True, seconds=18),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    casual = _config(
        base_score=1,
        fan_mode="linear",
        fan_cap=15,
        allow_chow=True,
        turn_timeout=TurnTimeout(enabled=False, seconds=15),
        kong_score=KongScore(enabled=False, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=False),
        draw_penalty=ToggleValue(enabled=False, value=0),
        rounds_per_game=4,
    )
    return {
        "generic_standard": standard,
        "generic_no_chow": no_chow,
        "generic_unrelated": with_unrelated,
        "generic_casual": casual,
    }


PRESETS: tuple[PresetTemplate, ...] = (
    PresetTemplate(
        template_code="generic_standard",
        template_name="家庭标准",
        description="底分 1，2 的 N 次方封顶 8 番，可以吃，限时 15 秒，杠分 1-2-1",
        config=preset_configs()["generic_standard"],
        sort_order=10,
    ),
    PresetTemplate(
        template_code="generic_no_chow",
        template_name="宽松无吃",
        description="不能吃只能碰，线性累加封顶 12 番，适合新手慢慢打",
        config=preset_configs()["generic_no_chow"],
        sort_order=20,
    ),
    PresetTemplate(
        template_code="generic_unrelated",
        template_name="带十三不靠",
        description="在家庭标准基础上开放十三不靠，需要 4 张牌间隔至少 3 位",
        config=preset_configs()["generic_unrelated"],
        sort_order=30,
    ),
    PresetTemplate(
        template_code="generic_casual",
        template_name="休闲不限时",
        description="出牌不限时、杠不计分、无听牌提示，纯粹图个乐",
        config=preset_configs()["generic_casual"],
        sort_order=40,
    ),
)

__all__ = ["PRESETS", "preset_configs"]
