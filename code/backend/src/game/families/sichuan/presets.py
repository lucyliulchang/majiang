"""四川族预置模板（03 §6）：`sichuan_default`。

口径：108 张、禁吃、强制缺一门、血战到底（多赢家）、起胡 0 番、
线性累加封顶 8 番、杠分刮风 1 / 下雨 2 / 补杠 1、查叫与查花猪默认关。
"""

from __future__ import annotations

from game.families.registry import PresetTemplate
from game.families.sichuan.config import (
    KongScore,
    RuleConfig,
    ToggleValue,
    TurnTimeout,
)


def preset_configs() -> dict[str, dict]:
    default = RuleConfig(
        base_score=1,
        fan_mode="linear",
        fan_cap=8,
        allow_chow=False,
        patterns={"standard": True, "seven_pairs": True, "long_seven_pairs": True},
        turn_timeout=TurnTimeout(enabled=True, seconds=15),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        draw_penalty=ToggleValue(enabled=False, value=0),
        lack_suit_required=True,
        multi_winner=True,
        min_fan_to_win=0,
        cha_jiao=ToggleValue(enabled=False, value=0),
        hua_zhu=ToggleValue(enabled=False, value=0),
        discard_pay_mode="single",
        rounds_per_game=4,
    ).model_dump()
    return {"sichuan_default": default}


PRESETS: tuple[PresetTemplate, ...] = (
    PresetTemplate(
        template_code="sichuan_default",
        template_name="四川血战到底",
        description="108 张、不能吃、必须缺一门、一家胡了继续打（最多三家胡）、刮风 1/下雨 2",
        config=preset_configs()["sichuan_default"],
        sort_order=10,
    ),
)

__all__ = ["PRESETS", "preset_configs"]
