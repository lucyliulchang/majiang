"""广东族牌型插件（03 §5）：standard / seven_pairs / thirteen_orphans。

与通用族的差别只在**番种口径**：
- 标准胡的基础番是「鸡胡 1 番」（推倒胡：能胡就有底番），不是通用的「平胡」；
- 通用番表里的门风/圈风/箭刻/一般高/三色同顺/字一色/门清不在广东 12 项里，
  因此这里根本不产出这些番种（即便产出了 `fan_of` 也会过滤掉，属于双保险）。

牌型判定本身复用 `game/families/generic/patterns/standard.py` 的拆解器与
`common.py` 的番种片段，避免两份互不相同的胡牌算法。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.families.generic.patterns.common import situational_fan_hits, suit_fan_hits
from game.families.generic.patterns.standard import decompositions
from game.hand import HandContext
from game.patterns.base import FanHit, register_pattern

if TYPE_CHECKING:
    from game.families.guangdong.config import RuleConfig

FAMILY = "guangdong"


def _sets_of(ctx: HandContext, sets) -> list[tuple[str, int]]:
    """把拆解结果与副露摊平成 (chow|pong, 起始牌)。杠按刻子计。"""
    kinds: list[tuple[str, int]] = list(sets)
    for meld in ctx.melds:
        if meld.kind in ("pong", "kong_exposed", "kong_hidden", "kong_added"):
            kinds.append(("pong", meld.tiles[0]))
        else:
            kinds.append(("chow", meld.tiles[0]))
    return kinds


class GuangdongStandardPattern:
    """推倒胡标准胡：4 面子 + 1 将，基础 1 番鸡胡。"""

    id = "standard"
    name = "标准胡"

    def match(self, ctx: HandContext) -> bool:
        if sum(ctx.counts) % 3 != 2:
            return False
        return bool(decompositions(ctx.counts, stop_at=1))

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        options = decompositions(ctx.counts)
        if not options:
            return []
        hits: list[FanHit] = [FanHit("ji_hu")]
        hits.extend(suit_fan_hits(ctx))
        hits.extend(situational_fan_hits(ctx, rule))
        if any(all(kind == "pong" for kind, _ in _sets_of(ctx, sets)) for _pair, sets in options):
            hits.append(FanHit("peng_peng_hu"))
        return hits


class GuangdongSevenPairsPattern:
    """七对 / 龙七对（4 张相同即龙七对）。"""

    id = "seven_pairs"
    name = "七对"

    def match(self, ctx: HandContext) -> bool:
        if ctx.melds or sum(ctx.counts) != 14:
            return False
        return all(count % 2 == 0 for count in ctx.counts)

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        hits: list[FanHit] = [FanHit("qi_dui")]
        if any(count == 4 for count in ctx.counts):
            hits.append(FanHit("long_qi_dui"))
        hits.extend(suit_fan_hits(ctx))
        hits.extend(situational_fan_hits(ctx, rule))
        return hits


class GuangdongThirteenOrphansPattern:
    """十三幺：13 种幺九字牌各一张 + 其中一张成对。"""

    id = "thirteen_orphans"
    name = "十三幺"

    ORPHANS = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)

    def match(self, ctx: HandContext) -> bool:
        if ctx.melds or sum(ctx.counts) != 14:
            return False
        if any(ctx.counts[tile] < 1 for tile in self.ORPHANS):
            return False
        if any(count and tile not in self.ORPHANS for tile, count in enumerate(ctx.counts)):
            return False
        return sum(1 for tile in self.ORPHANS if ctx.counts[tile] == 2) == 1

    def calc_fan(self, ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
        hits: list[FanHit] = [FanHit("shi_san_yao")]
        hits.extend(situational_fan_hits(ctx, rule))
        return hits


register_pattern(GuangdongStandardPattern, FAMILY)
register_pattern(GuangdongSevenPairsPattern, FAMILY)
register_pattern(GuangdongThirteenOrphansPattern, FAMILY)

__all__ = [
    "GuangdongSevenPairsPattern",
    "GuangdongStandardPattern",
    "GuangdongThirteenOrphansPattern",
]
