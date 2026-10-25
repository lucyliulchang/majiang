"""十三幺：13 种幺九字牌各一张 + 其中任意一张成对。"""

from app.game.hand import HandContext
from app.game.patterns.base import FanHit, register_pattern
from app.game.patterns.common import situational_fan_hits
from app.schemas.rule import RuleConfig

ORPHANS = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)


class ThirteenOrphansPattern:
    id = "thirteen_orphans"
    name = "十三幺"

    def match(self, ctx: HandContext) -> bool:
        if ctx.melds:
            return False
        if sum(ctx.counts) != 14:
            return False
        for tile in ORPHANS:
            if ctx.counts[tile] < 1:
                return False
        # 这 13 种之外不能有别的牌，且正好有且只有一种成对
        outside = sum(c for tile, c in enumerate(ctx.counts) if tile not in ORPHANS)
        if outside:
            return False
        pairs = sum(1 for tile in ORPHANS if ctx.counts[tile] == 2)
        return pairs == 1

    def calc_fan(self, ctx: HandContext, rule: RuleConfig) -> list[FanHit]:
        hits: list[FanHit] = [FanHit("shi_san_yao")]
        hits.extend(situational_fan_hits(ctx, rule))
        return hits


register_pattern(ThirteenOrphansPattern)
