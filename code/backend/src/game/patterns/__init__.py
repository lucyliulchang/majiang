"""跨族牌型工具：注册表门面 + 统一胡牌判定入口。

族的牌型插件放在 `game/families/{engineCode}/patterns/`，导入即注册（同 id 全局唯一，
见 03 §2.2）。本模块**不**导入任何具体族，避免骨架反向依赖插件：

- `game/families/generic/patterns/` 由 `game.families` 导入；
- 若调用方只导入了骨架（例如直接跑单测），`_ensure_registered()` 会兜底加载通用族牌型，
  防止「注册表空 → 永远胡不了」的静默故障。

族归属（S7）取自 `rule.family_code`（配置模型的类属性，不是字段）：
`generic` / `guangdong` / `sichuan` / `baishi` 各自只看自己可见的牌型集合。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.hand import HandContext
from game.patterns.base import (  # noqa: F401  对外统一出口
    FAMILY_REGISTRY,
    REGISTRY,
    FanHit,
    WinResult,
    get_pattern,
    patterns_for,
    register_pattern,
)

if TYPE_CHECKING:
    from game.families.generic.config import RuleConfig

__all__ = [
    "FAMILY_REGISTRY",
    "REGISTRY",
    "FanHit",
    "WinResult",
    "get_pattern",
    "patterns_for",
    "register_pattern",
    "registered_ids",
    "collect_wins",
    "is_winning",
    "winning_tiles",
    "match_pattern",
    "family_of",
]


def _ensure_registered() -> None:
    """注册表为空时兜底加载通用族牌型（导入期自检也会调用，见 families/registry.py）。"""
    if REGISTRY:
        return
    import game.families.generic.patterns  # noqa: F401  导入即注册


def family_of(rule) -> str:
    """配置模型声明的族编码；缺失时退回 `generic`（旧模板仍可解析）。"""
    return str(getattr(rule, "family_code", None) or "generic")


def registered_ids(family: str | None = None) -> list[str]:
    _ensure_registered()
    return list(patterns_for(family).keys())


def match_pattern(pattern_id: str, ctx: HandContext, rule: "RuleConfig") -> bool:
    _ensure_registered()
    pattern = get_pattern(pattern_id, family_of(rule))
    if pattern is None or not rule.is_pattern_enabled(pattern_id):
        return False
    rule_based = getattr(pattern, "match_with_rule", None)
    if callable(rule_based):
        return bool(rule_based(ctx, rule))
    return bool(pattern.match(ctx))


def collect_wins(ctx: HandContext, rule: "RuleConfig") -> list[WinResult]:
    """遍历本族牌型，收集所有命中的牌型（可能多个，例如七对同时也是标准胡）。"""
    _ensure_registered()
    results: list[WinResult] = []
    for pattern_id, pattern in patterns_for(family_of(rule)).items():
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


def is_winning(ctx: HandContext, rule: "RuleConfig") -> bool:
    for pattern_id in registered_ids(family_of(rule)):
        if match_pattern(pattern_id, ctx, rule):
            return True
    return False


def winning_tiles(ctx: HandContext, rule: "RuleConfig") -> list[int]:
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
