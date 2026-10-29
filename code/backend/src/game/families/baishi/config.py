"""柏氏规则族 `baishi` 的配置（07 §10 §11）。

与通用族的差别（数值一律以 07 为准，不得臆造）：
- `fan_combine = sum_all`：累计不乘积，同互斥组只取最高；
- `fan_cap` 只能为空（不封顶），模板填了封顶由 `ruleService` 报 `RULE_FAN_CAP_UNSUPPORTED`；
- `fan_mode` 只有 `linear`（U = 底分 × 番合计）；
- `min_fan_to_win = 1`（起胡 1 番）；
- 倍数：`self_draw_multiplier = 2`、`dealer_rule = {win:2, pay:2}`，三者叠加；
- 包牌 `bao_pai`：仅点炮 + ≥3 明牌 + 命中 清一色/混一色/全文字/全幺 + 点炮牌属于该牌型；
- 杠分：明杠 1、暗杠 2、补杠 1，**三家各付**（`pay_mode = all`）；
- 抢杠：只有明杠可被抢（`rob_kong_kinds = ("exposed",)`）；
- 暂停：`pause.enabled=true`，房态 `paused` 由 `realtime/room.py` 落地。
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, model_validator

from game.families.baishi.fan import FAN_DEFAULTS, FAN_NAMES, STACKABLE_FANS
from game.families.generic.config import FanItem as _GenericFanItem
from game.families.generic.config import PatternSwitches as _PatternSwitches
from game.families.generic.config import ToggleValue, TurnTimeout
from game.families.generic.config import _StrictModel

ROUNDS_PER_GAME = 4


class FanItem(_GenericFanItem):
    """柏氏番值上限 120（全文字七对），其余校验口径与通用族一致。"""

    FAN_MAX = 200

#: 包牌可选的四种牌型（07 §7.1）
BAO_PAI_PATTERN_CHOICES = ("qing_yi_se", "hun_yi_se", "quan_zi", "quan_yao")


def default_fan_table() -> list[FanItem]:
    """07 §5 的 32 项番表。"""
    return [
        FanItem(id=fid, name=name, fan=fan, exclusive_group=group, stackable=fid in STACKABLE_FANS)
        for fid, name, fan, group, _counting in FAN_DEFAULTS
    ]


class BaishiThirteenUnrelated(_StrictModel):
    """13不靠的口径由 07 §6.3.4 固定，模板只保留开/关。"""

    enabled: bool = True


class PatternSwitches(_PatternSwitches):
    """柏氏牌型：标准胡 / 七对 / 13不靠 / 十三幺（07 §11）。"""

    standard: bool = True
    seven_pairs: bool = True
    thirteen_orphans: bool = True
    thirteen_unrelated: BaishiThirteenUnrelated = Field(default_factory=BaishiThirteenUnrelated)


class DealerRule(_StrictModel):
    """庄家倍数（07 §3.2）：胡牌者是庄家 → 所有付款方翻；付款方是庄家 → 该家翻。"""

    win_multiplier: int = 2
    pay_multiplier: int = 2


class BaoPaiOptions(_StrictModel):
    """包牌（07 §7.1）：四条全满足才由点炮者独付三家之和。"""

    enabled: bool = True
    win_type: Literal["discard"] = "discard"
    min_exposed_melds: int = 3
    patterns: list[str] = Field(default_factory=lambda: list(BAO_PAI_PATTERN_CHOICES))
    payer: Literal["discarder_full"] = "discarder_full"


class BaishiKongScore(_StrictModel):
    """杠分：明杠 1 / 暗杠 2 / 补杠 1，`pay_mode=all` 即三家各付（07 §8）。"""

    enabled: bool = True
    exposed: int = 1
    hidden: int = 2
    added: int = 1
    pay_mode: Literal["all", "discarder"] = "all"


class PauseToggle(_StrictModel):
    enabled: bool = True


class RuleConfig(_StrictModel):
    """柏氏规则参数（快照 `config` 的完整形状，07 §10 逐字段）。"""

    family_code: ClassVar[str] = "baishi"
    #: 只有明杠可被抢（07 §6.5.4）：补杠、暗杠不开抢杠窗口
    rob_kong_kinds: ClassVar[tuple[str, ...]] = ("exposed",)

    base_score: int = 1
    fan_mode: Literal["linear", "exponential"] = "linear"
    fan_combine: Literal["group_best", "sum_all"] = "sum_all"
    fan_cap: int | None = None
    min_fan_to_win: int = 1
    fan_table: list[FanItem] = Field(default_factory=default_fan_table)
    patterns: PatternSwitches = Field(default_factory=PatternSwitches)
    allow_chow: bool = True
    multi_winner: bool = False
    self_draw_multiplier: int = 2
    dealer_rule: DealerRule = Field(default_factory=DealerRule)
    discard_pay_mode: Literal["single", "all"] = "all"
    bao_pai: BaoPaiOptions = Field(default_factory=BaoPaiOptions)
    kong_score: BaishiKongScore = Field(default_factory=BaishiKongScore)
    # 07 未定义「荒庄罚分」：capability.switches 也不含 draw_penalty，
    # 这里不能留字段——留了就会让预置模板/新建模板带上族不支持的开关，
    # 开桌在被 `_assertCapability` 拒绝（RULE_SWITCH_UNSUPPORTED），整族不可用。
    turn_timeout: TurnTimeout = Field(default_factory=lambda: TurnTimeout(enabled=False, seconds=0))
    pause: PauseToggle = Field(default_factory=PauseToggle)
    rounds_per_game: int = ROUNDS_PER_GAME
    claim_window_seconds: int = 8

    @model_validator(mode="after")
    def _cross_check(self):
        if not 1 <= self.base_score <= 100:
            raise ValueError("底分必须在 1-100 之间")
        if not 0 <= self.min_fan_to_win <= 100:
            raise ValueError("起胡番数必须在 0-100 之间")
        if self.min_fan_to_win < 1:
            raise ValueError("柏氏起胡番数为 1，不得低于 1 番")
        if not 1 <= self.self_draw_multiplier <= 10:
            raise ValueError("自摸/庄家倍率必须在 1-10 之间")
        for label, value in (
            ("庄家胡倍率", self.dealer_rule.win_multiplier),
            ("庄家付倍率", self.dealer_rule.pay_multiplier),
        ):
            if not 1 <= value <= 10:
                raise ValueError(f"{label}必须在 1-10 之间")
        if self.rounds_per_game != ROUNDS_PER_GAME:
            raise ValueError("一圈固定 4 个庄次（北位下庄结束），不支持自定义局数")
        if not 3 <= self.claim_window_seconds <= 30:
            raise ValueError("碰杠胡询问窗口必须在 3-30 秒之间")
        if not self.fan_table:
            raise ValueError("番种表不能为空，至少要保留一个番种")
        seen: set[str] = set()
        for item in self.fan_table:
            if item.id in seen:
                raise ValueError(f"番种标识「{item.id}」重复，同一模板内必须唯一")
            seen.add(item.id)
        if self.turn_timeout.enabled and not 10 <= self.turn_timeout.seconds <= 120:
            raise ValueError("出牌限时必须在 10-120 秒之间")
        if self.kong_score.enabled:
            for label, value in (
                ("明杠", self.kong_score.exposed),
                ("暗杠", self.kong_score.hidden),
                ("补杠", self.kong_score.added),
            ):
                if not 0 <= value <= 20:
                    raise ValueError(f"{label}分数必须在 0-20 之间")
        if not any(
            (
                self.patterns.standard,
                self.patterns.seven_pairs,
                self.patterns.thirteen_orphans,
                bool(getattr(self.patterns.thirteen_unrelated, "enabled", False)),
            )
        ):
            raise ValueError("至少要启用一种胡牌牌型，否则这局永远胡不了")
        if self.bao_pai.enabled:
            if not self.bao_pai.patterns:
                raise ValueError("包牌至少要选一种牌型，且明牌组数须在 2-4 之间")
            if not 2 <= self.bao_pai.min_exposed_melds <= 4:
                raise ValueError("包牌至少要选一种牌型，且明牌组数须在 2-4 之间")
            unknown = [p for p in self.bao_pai.patterns if p not in BAO_PAI_PATTERN_CHOICES]
            if unknown:
                raise ValueError("包牌至少要选一种牌型，且明牌组数须在 2-4 之间")
        return self

    # ---- 引擎侧的安全取值 ----
    def kong_points(self, kind: str) -> int:
        if not self.kong_score.enabled:
            return 0
        return {
            "exposed": self.kong_score.exposed,
            "hidden": self.kong_score.hidden,
            "added": self.kong_score.added,
        }.get(kind, 0)

    def is_pattern_enabled(self, pattern_id: str) -> bool:
        if pattern_id == "standard":
            return self.patterns.standard
        if pattern_id == "seven_pairs":
            return self.patterns.seven_pairs
        if pattern_id == "thirteen_orphans":
            return self.patterns.thirteen_orphans
        if pattern_id == "thirteen_unrelated":
            return bool(getattr(self.patterns.thirteen_unrelated, "enabled", False))
        return False

    def fan_of(self, fan_id: str) -> FanItem | None:
        for item in self.fan_table:
            if item.id == fan_id:
                return item
        return None

    def fan_name(self, fan_id: str) -> str:
        item = self.fan_of(fan_id)
        return item.name if item else FAN_NAMES.get(fan_id, fan_id)

    def brief(self) -> dict:
        """牌桌顶部与战绩详情用的规则摘要。"""
        return {
            "base_score": self.base_score,
            "fan_mode": self.fan_mode,
            "fan_cap": None,
            "allow_chow": self.allow_chow,
            "turn_timeout": {
                "enabled": self.turn_timeout.enabled,
                "seconds": self.turn_timeout.seconds if self.turn_timeout.enabled else None,
            },
            "kong_score": {
                "enabled": self.kong_score.enabled,
                "exposed": self.kong_score.exposed if self.kong_score.enabled else 0,
                "hidden": self.kong_score.hidden if self.kong_score.enabled else 0,
                "added": self.kong_score.added if self.kong_score.enabled else 0,
            },
            "ting_hint": False,
            "patterns": [
                name
                for key, name in (
                    ("standard", "标准胡"),
                    ("seven_pairs", "七对"),
                    ("thirteen_orphans", "十三幺"),
                    ("thirteen_unrelated", "十三不靠"),
                )
                if self.is_pattern_enabled(key)
            ],
            "rounds_per_game": self.rounds_per_game,
            "bao_pai": self.bao_pai.enabled,
            "self_draw_multiplier": self.self_draw_multiplier,
            "dealer_multiplier": {
                "win": self.dealer_rule.win_multiplier,
                "pay": self.dealer_rule.pay_multiplier,
            },
            "min_fan_to_win": self.min_fan_to_win,
            "pause": self.pause.enabled,
        }


__all__ = [
    "BAO_PAI_PATTERN_CHOICES",
    "BaoPaiOptions",
    "BaishiKongScore",
    "BaishiThirteenUnrelated",
    "DealerRule",
    "FanItem",
    "PauseToggle",
    "PatternSwitches",
    "ROUNDS_PER_GAME",
    "RuleConfig",
    "ToggleValue",
    "TurnTimeout",
    "default_fan_table",
]
