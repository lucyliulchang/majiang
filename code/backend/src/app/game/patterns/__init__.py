"""导入即注册所有牌型，并对外提供统一的胡牌判定入口。"""

from app.game.hand import HandContext
from app.game.patterns import seven_pairs, standard, thirteen_orphans, thirteen_unrelated  # noqa: F401
from app.game.patterns.base import REGISTRY, FanHit, WinResult, get_pattern, registered_ids
from app.schemas.rule import RuleConfig

__all__ = [
    "REGISTRY",
    "FanHit",
    "WinResult",
    "get_pattern",
    "registered_ids",
    "collect_wins",
    "is_winning",
    "winning_tiles",
    "match_pattern",
]


def match_pattern(pattern_id: str, ctx: HandContext, rule: RuleConfig) -> bool:
    pattern = get_pattern(pattern_id)
    if pattern is None or not rule.is_pattern_enabled(pattern_id):
        return False
    rule_based = getattr(pattern, "match_with_rule", None)
    if callable(rule_based):
        return bool(rule_based(ctx, rule))
    return bool(pattern.match(ctx))


def collect_wins(ctx: HandContext, rule: RuleConfig) -> list[WinResult]:
    """遍历注册表，收集所有命中的牌型（可能多个，例如七对同时也是标准胡）。"""
    results: list[WinResult] = []
    for pattern_id, pattern in REGISTRY.items():
        if not rule.is_pattern_enabled(pattern_id):
            continue
        rule_based = getattr(pattern, "match_with_rule", None)
        try:
            matched = bool(rule_based(ctx, rule)) if callable(rule_based) else bool(pattern.match(ctx))
        except (ValueError, KeyError, IndexError):
            matched = False
        if not matched:
            continue
        try:
            fan_hits = pattern.calc_fan(ctx, rule)
        except (ValueError, KeyError, IndexError):
            fan_hits = []
        results.append(WinResult(pattern_id=pattern_id, pattern_name=pattern.name, fan_hits=fan_hits))
    return results


def is_winning(ctx: HandContext, rule: RuleConfig) -> bool:
    for pattern_id in REGISTRY:
        if match_pattern(pattern_id, ctx, rule):
            return True
    return False


def winning_tiles(ctx: HandContext, rule: RuleConfig) -> list[int]:
    """听牌计算：把 34 种牌各试一次。14 张手牌入参时应先减去刚摸到的那张。"""
    result: list[int] = []
    base = list(ctx.counts)
    for tile in range(34):
        if base[tile] >= 4:
            continue
        base[tile] += 1
        probe = HandContext(
            counts=base,
            melds=ctx.melds,
            win_tile=tile,
            is_self_draw=True,
            seat_wind=ctx.seat_wind,
            round_wind=ctx.round_wind,
        )
        if is_winning(probe, rule):
            result.append(tile)
        base[tile] -= 1
    return result
