"""柏氏牌型插件（07 §5 §6）：standard / seven_pairs / thirteen_unrelated / thirteen_orphans。

牌型 id 与通用族同名，靠 `register_pattern(..., "baishi")` 注册到族内注册表覆盖实现
（`game/patterns/base.py` 的族内优先级），因此全局注册表里的通用实现不受影响。
番种判定全部在 `baishi/fan.py`，这里只做「命中哪一类牌型」的路由。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.families.baishi import fan as baishi_fan
from game.hand import HandContext
from game.patterns.base import FanHit, register_pattern

if TYPE_CHECKING:
    from game.families.baishi.config import RuleConfig

FAMILY = "baishi"


class BaishiStandardPattern:
    """4 面子 + 1 将；一手牌多解时逐解取最高总分（07 §6.1）。"""

    id = "standard"
    name = "标准胡"

    def match(self, ctx: HandContext) -> bool:
        return bool(baishi_fan.shapes(ctx, cap=1))

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        return baishi_fan.best_shape_fans(ctx, rule)


class BaishiSevenPairsPattern:
    """七小对（含全幺七对 / 全文字七对）；4 张相同算两对。"""

    id = "seven_pairs"
    name = "七小对"

    def match(self, ctx: HandContext) -> bool:
        return baishi_fan.is_seven_pairs(ctx)

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        return baishi_fan.seven_pairs_fans(ctx)


class BaishiThirteenUnrelatedPattern:
    """13不靠（07 §6.3.4）：中发白齐 + 三门数牌各 3 张同组。"""

    id = "thirteen_unrelated"
    name = "13不靠"

    def match(self, ctx: HandContext) -> bool:
        return baishi_fan.unrelated_pair(ctx) is not None

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        pair = baishi_fan.unrelated_pair(ctx)
        if pair is None:
            return []
        return baishi_fan.thirteen_unrelated_fans(ctx, pair)


class BaishiThirteenOrphansPattern:
    """十三幺（07 §6.3.6）：100 + 幺将 1 + 门清 1 = 102。"""

    id = "thirteen_orphans"
    name = "十三幺"

    def match(self, ctx: HandContext) -> bool:
        return baishi_fan.is_thirteen_orphans(ctx)

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        return baishi_fan.thirteen_orphans_fans(ctx)


register_pattern(BaishiStandardPattern, FAMILY)
register_pattern(BaishiSevenPairsPattern, FAMILY)
register_pattern(BaishiThirteenUnrelatedPattern, FAMILY)
register_pattern(BaishiThirteenOrphansPattern, FAMILY)

__all__ = [
    "BaishiSevenPairsPattern",
    "BaishiStandardPattern",
    "BaishiThirteenOrphansPattern",
    "BaishiThirteenUnrelatedPattern",
]
