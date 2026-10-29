"""广东族预置模板（03 §5）：`guangdong_default`。

口径：底分 1、线性累加、封顶 8 番（可选 4/6/8/10/不封顶）、可吃、限时 15 秒、
杠分 1-2-1、点炮独付、4 局；番表 12 项。
"""

from __future__ import annotations

from game.families.guangdong.config import (
    GUANGDONG_DEFAULT_FAN_CAP,
    KongScore,
    RuleConfig,
    ToggleValue,
    TurnTimeout,
)
from game.families.registry import PresetTemplate


def preset_configs() -> dict[str, dict]:
    """templateCode → config（种子与逐字段比对共用）。"""
    default = RuleConfig(
        base_score=1,
        fan_mode="linear",
        fan_cap=GUANGDONG_DEFAULT_FAN_CAP,
        allow_chow=True,
        turn_timeout=TurnTimeout(enabled=False, seconds=0),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        draw_penalty=ToggleValue(enabled=False, value=0),
        discard_pay_mode="single",
        rounds_per_game=4,
    ).model_dump()
    return {"guangdong_default": default}


PRESETS: tuple[PresetTemplate, ...] = (
    PresetTemplate(
        template_code="guangdong_default",
        template_name="广东推倒胡",
        description="底分 1、线性累加封顶 8 番、可以吃、限时 15 秒、杠分 1-2-1、点炮独付",
        config=preset_configs()["guangdong_default"],
        sort_order=10,
    ),
)

__all__ = ["PRESETS", "preset_configs"]
