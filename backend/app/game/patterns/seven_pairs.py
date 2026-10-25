"""七对（含龙七对：其中有 4 张相同）。要求门前清、14 张、全部成对。"""

from app.game.hand import HandContext
from app.game.patterns.base import FanHit, register_pattern
from app.game.patterns.common import situational_fan_hits, suit_fan_hits
from app.schemas.rule import RuleConfig


class SevenPairsPattern:
    id = "seven_pairs"
    name = "七对"

    def match(self, ctx: HandContext) -> bool:
        if ctx.melds:
            return False
        if sum(ctx.counts) != 14:
            return False
        return all(count % 2 == 0 for count in ctx.counts)

    def calc_fan(self, ctx: HandContext, rule: RuleConfig) -> list[FanHit]:
        hits: list[FanHit] = [FanHit("qi_dui")]
        if any(count == 4 for count in ctx.counts):
            hits.append(FanHit("long_qi_dui"))
        hits.extend(suit_fan_hits(ctx))
        hits.extend(situational_fan_hits(ctx, rule))
        return hits


register_pattern(SevenPairsPattern)
