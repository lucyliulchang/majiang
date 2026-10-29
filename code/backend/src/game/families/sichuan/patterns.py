"""四川族牌型插件（03 §6）：`long_seven_pairs`（龙七对）。

`standard` / `seven_pairs` 直接复用通用族实现（108 张牌墙里没有字牌，通用判定天然成立），
这里只补 03 §6 里点名、但通用族没有单独注册的「龙七对」牌型：
七对且至少有一组四张相同。

龙七对同时也是七对，`collect_wins` 会两条都命中，`best_win` 取番数更高的那一条；
两条的番种集合一致（`qi_dui` + `long_qi_dui`），所以不会因为多命中一条而虚高。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.families.generic.patterns.common import situational_fan_hits, suit_fan_hits
from game.hand import HandContext
from game.patterns.base import FanHit, register_pattern

if TYPE_CHECKING:
    from game.families.sichuan.config import RuleConfig

FAMILY = "sichuan"


class LongSevenPairsPattern:
    id = "long_seven_pairs"
    name = "龙七对"

    def match(self, ctx: HandContext) -> bool:
        if ctx.melds or sum(ctx.counts) != 14:
            return False
        if not all(count % 2 == 0 for count in ctx.counts):
            return False
        return any(count == 4 for count in ctx.counts)

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        hits: list[FanHit] = [FanHit("qi_dui"), FanHit("long_qi_dui")]
        hits.extend(suit_fan_hits(ctx))
        hits.extend(situational_fan_hits(ctx, rule))
        return hits


register_pattern(LongSevenPairsPattern, FAMILY)

__all__ = ["LongSevenPairsPattern"]
