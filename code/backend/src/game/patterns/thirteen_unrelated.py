"""十三不靠 / 七星不靠。

各地定义差异大（是否要求七种字牌齐全、是否允许一对将、数牌间隔几位），
所以这里完全由规则模板的参数驱动，改规则不改代码。
"""

from game.hand import HandContext
from game.patterns.base import FanHit, register_pattern
from game.patterns.common import situational_fan_hits
from schemas.rule import RuleConfig, ThirteenUnrelatedOptions


class ThirteenUnrelatedPattern:
    id = "thirteen_unrelated"
    name = "十三不靠"

    def match(self, ctx: HandContext) -> bool:
        """无规则上下文时用默认参数判断，引擎实际走 match_with_rule。"""
        return self.match_with_rule(ctx, RuleConfig())

    def match_with_rule(self, ctx: HandContext, rule: RuleConfig) -> bool:
        options: ThirteenUnrelatedOptions = rule.patterns.thirteen_unrelated
        if not options.enabled:
            return False
        if ctx.melds:
            return False
        total = sum(ctx.counts)
        if total not in (13, 14):
            return False

        pair_used = False
        for tile, count in enumerate(ctx.counts):
            if count <= 1:
                continue
            if count == 2 and options.allow_pair and not pair_used:
                pair_used = True
                continue
            return False

        if options.require_all_honors:
            honor_kinds = sum(1 for tile in range(27, 34) if ctx.counts[tile] > 0)
            if honor_kinds < 7:
                return False

        for suit in range(3):
            base = suit * 9
            ranks = [rank for rank in range(9) if ctx.counts[base + rank] > 0]
            for left, right in zip(ranks, ranks[1:]):
                if right - left < options.min_gap:
                    return False
        return True

    def calc_fan(self, ctx: HandContext, rule: RuleConfig) -> list[FanHit]:
        hits: list[FanHit] = [FanHit("shi_san_bu_kao")]
        hits.extend(situational_fan_hits(ctx, rule))
        return hits


register_pattern(ThirteenUnrelatedPattern)
