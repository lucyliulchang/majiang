"""广东族配置（首期骨架）。

03 §5：首期**复用通用引擎 + 广东番表/开关预设**，不新增结算规则。
广东 12 项番表与专属预置模板留在 S7 落地；在此之前沿用通用配置模型，
保证「族可列、模板可存、可开桌」的现有行为不变。
"""

from game.families.generic.config import (  # noqa: F401  首期同构，S7 替换为 12 项番表
    FanItem,
    KongScore,
    PatternSwitches,
    RuleConfig,
    ThirteenUnrelatedOptions,
    ToggleValue,
    TurnTimeout,
)

__all__ = [
    "FanItem",
    "KongScore",
    "PatternSwitches",
    "RuleConfig",
    "ThirteenUnrelatedOptions",
    "ToggleValue",
    "TurnTimeout",
]
