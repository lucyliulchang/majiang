"""通用族引擎适配层（03 §3.1）。

`generic` 的牌路与通用骨架完全一致，因此这里只做三件事：
1. 声明族标识与牌张集合（136）；
2. 把配置收纳成 `RuleConfig`（允许上层直接给 dict，例如从快照恢复）；
3. 暴露 `create_engine()` 供 `families/registry.py` 作为 EngineFactory。

行为口径与 S6 之前逐字节一致：番值、优先级、结算公式都不在适配层里。
"""

from __future__ import annotations

from game.engine import GameEngine
from game.families.generic.config import RuleConfig
from game.tiles import TILE_SET_136


class GenericEngine(GameEngine):
    """通用家庭标准：136 张、可吃、单赢家、同组取最高番。"""

    family_code = "generic"
    tile_set_code = TILE_SET_136


def create_engine(rule, seats, **kwargs) -> GenericEngine:
    """EngineFactory：`rule` 可为 RuleConfig 或等价的 dict / 快照 config。"""
    if not isinstance(rule, RuleConfig):
        rule = RuleConfig.model_validate(rule or {})
    return GenericEngine(rule, seats, **kwargs)


__all__ = ["GenericEngine", "create_engine"]
