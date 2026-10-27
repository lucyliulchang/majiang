"""番种求值：互斥组去重 → requires 校验 → 汇总 → 封顶 → 折算分数。

番种不是写死在代码里，而是规则模板的一部分（fan_table），
用户加一个自定义番种只需在界面加一行。
"""

from collections import defaultdict
from dataclasses import dataclass, field

from game.patterns.base import WinResult
from schemas.rule import FanItem, RuleConfig

_MAX_EXPONENT = 20


@dataclass
class FanLine:
    id: str
    name: str
    fan: int
    count: int = 1

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "fan": self.fan, "count": self.count}


@dataclass
class ScoreBreakdown:
    pattern_id: str
    pattern_name: str
    lines: list[FanLine] = field(default_factory=list)
    fan_raw: int = 0
    fan_total: int = 0
    capped: bool = False
    score: int = 0

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "lines": [line.to_dict() for line in self.lines],
            "fan_raw": self.fan_raw,
            "fan_total": self.fan_total,
            "capped": self.capped,
            "score": self.score,
        }


def score_from_fan(fan_total: int, rule: RuleConfig) -> int:
    if rule.fan_mode == "linear":
        return rule.base_score * max(1, fan_total)
    exponent = max(0, min(fan_total, _MAX_EXPONENT))
    return rule.base_score * (2**exponent)


def evaluate(win: WinResult, rule: RuleConfig) -> ScoreBreakdown:
    occurrences: list[FanItem] = []
    for hit in win.fan_hits:
        item = rule.fan_of(hit.id)
        if item is None:
            continue
        repeat = hit.count if item.stackable else 1
        occurrences.extend([item] * max(0, repeat))

    plain: list[FanItem] = []
    grouped: dict[str, list[FanItem]] = defaultdict(list)
    for item in occurrences:
        if item.exclusive_group:
            grouped[item.exclusive_group].append(item)
        else:
            plain.append(item)

    kept: list[FanItem] = list(plain)
    for items in grouped.values():
        kept.append(max(items, key=lambda entry: entry.fan))

    tally: dict[str, FanLine] = {}
    for item in kept:
        if item.id in tally:
            tally[item.id].count += 1
        else:
            tally[item.id] = FanLine(id=item.id, name=item.name, fan=item.fan)

    # 让结算面板按番值从高到低展示，家人一眼看出大牌在哪
    lines = sorted(tally.values(), key=lambda line: (-line.fan, line.id))
    fan_raw = sum(line.fan * line.count for line in lines)
    capped = rule.fan_cap is not None and fan_raw > rule.fan_cap
    fan_total = rule.fan_cap if capped else fan_raw

    return ScoreBreakdown(
        pattern_id=win.pattern_id,
        pattern_name=win.pattern_name,
        lines=lines,
        fan_raw=fan_raw,
        fan_total=fan_total or 0,
        capped=bool(capped),
        score=score_from_fan(fan_total or 0, rule),
    )


def best_win(wins: list[WinResult], rule: RuleConfig) -> ScoreBreakdown | None:
    best: ScoreBreakdown | None = None
    for win in wins:
        breakdown = evaluate(win, rule)
        if best is None:
            best = breakdown
            continue
        if (breakdown.score, breakdown.fan_total) > (best.score, best.fan_total):
            best = breakdown
    return best
