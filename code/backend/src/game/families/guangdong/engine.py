"""广东族引擎适配层（03 §5 首期骨架：复用通用骨架）。

差异只有族标识与能力声明；结算与牌路沿用通用骨架，S7 再按广东番表补齐。
"""

from __future__ import annotations

from game.families.guangdong.config import RuleConfig
from game.families.registry import coerce_config
from game.families.generic.engine import GenericEngine


class GuangdongEngine(GenericEngine):
    """广东推倒胡（136 张、可吃、单赢家）。"""

    family_code = "guangdong"
    tile_set_code = "136"


def create_engine(rule, seats, **kwargs) -> GuangdongEngine:
    return GuangdongEngine(coerce_config(rule, RuleConfig), seats, **kwargs)


__all__ = ["GuangdongEngine", "create_engine"]
