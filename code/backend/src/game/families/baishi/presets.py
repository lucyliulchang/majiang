"""柏氏族预置模板（07 §10）：`baishi_default`。

一条模板即 07 §10 的默认 config：32 项番表、累计不乘积、不封顶、起胡 1 番、
自摸 ×2 + 庄家 ×2、点炮三家各付、包牌独付、杠分 1/2/1 三家各付、不限时、可暂停。
"""

from __future__ import annotations

from game.families.baishi.config import (
    BaoPaiOptions,
    BaishiKongScore,
    DealerRule,
    PauseToggle,
    RuleConfig,
    TurnTimeout,
)
from game.families.registry import PresetTemplate


def preset_configs() -> dict[str, dict]:
    default = RuleConfig(
        base_score=1,
        fan_mode="linear",
        fan_combine="sum_all",
        fan_cap=None,
        min_fan_to_win=1,
        allow_chow=True,
        multi_winner=False,
        self_draw_multiplier=2,
        dealer_rule=DealerRule(win_multiplier=2, pay_multiplier=2),
        discard_pay_mode="all",
        bao_pai=BaoPaiOptions(
            enabled=True,
            win_type="discard",
            min_exposed_melds=3,
            patterns=["qing_yi_se", "hun_yi_se", "quan_zi", "quan_yao"],
            payer="discarder_full",
        ),
        kong_score=BaishiKongScore(enabled=True, exposed=1, hidden=2, added=1, pay_mode="all"),
        turn_timeout=TurnTimeout(enabled=False, seconds=0),
        pause=PauseToggle(enabled=True),
        rounds_per_game=4,
        claim_window_seconds=8,
    ).model_dump()
    return {"baishi_default": default}


PRESETS: tuple[PresetTemplate, ...] = (
    PresetTemplate(
        template_code="baishi_default",
        template_name="柏氏标准",
        description="32 项番表累计不乘积、不封顶、起胡 1 番、自摸×2+庄家×2、包牌独付、杠分 1/2/1",
        config=preset_configs()["baishi_default"],
        sort_order=10,
    ),
)

__all__ = ["PRESETS", "preset_configs"]
