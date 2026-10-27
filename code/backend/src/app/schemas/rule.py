"""规则模板的强校验模型。

三组可选规则项（出牌超时 / 杠分 / 听牌提示）统一采用「enabled + 从属值」模型：
- enabled=True 时才校验从属值范围
- enabled=False 时既不校验也不取用，但保留原值，方便来回切换
绝不用 0 / null / -1 表示"未启用"。
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

PATTERN_NAMES: dict[str, str] = {
    "standard": "标准胡（4 面子 + 1 将）",
    "seven_pairs": "七对",
    "thirteen_orphans": "十三幺",
    "thirteen_unrelated": "十三不靠",
}

# 番种标识的中文名，用于界面与结算展示
FAN_NAMES: dict[str, str] = {
    "ping_hu": "平胡",
    "zi_mo": "自摸",
    "men_qian": "门前清",
    "peng_peng_hu": "碰碰胡",
    "qing_yi_se": "清一色",
    "hun_yi_se": "混一色",
    "zi_yi_se": "字一色",
    "qi_dui": "七对",
    "long_qi_dui": "龙七对",
    "shi_san_yao": "十三幺",
    "shi_san_bu_kao": "十三不靠",
    "kong": "杠",
    "hai_di": "海底捞月",
    "gang_shang_hua": "杠上开花",
    "qiang_gang_hu": "抢杠胡",
    "men_feng": "门风",
    "quan_feng": "圈风",
    "jian_ke": "箭刻",
    "yi_ban_gao": "一般高",
    "san_se_tong_shun": "三色同顺",
}


def _default_fan_table() -> list["FanItem"]:
    raw = [
        ("ping_hu", 1, "structure", False),
        ("peng_peng_hu", 2, "structure", False),
        ("qing_yi_se", 6, "suit", False),
        ("hun_yi_se", 2, "suit", False),
        ("zi_yi_se", 8, "suit", False),
        ("qi_dui", 4, "special", False),
        ("long_qi_dui", 8, "special", False),
        ("shi_san_yao", 8, "special", False),
        ("shi_san_bu_kao", 8, "special", False),
        ("zi_mo", 1, None, False),
        ("men_qian", 1, None, False),
        ("kong", 1, None, True),
        ("hai_di", 1, None, False),
        ("gang_shang_hua", 1, None, False),
        ("qiang_gang_hu", 1, None, False),
        ("men_feng", 1, None, False),
        ("quan_feng", 1, None, False),
        ("jian_ke", 1, None, False),
        ("yi_ban_gao", 1, "same", False),
        ("san_se_tong_shun", 1, "same", False),
    ]
    return [
        FanItem(id=fid, name=FAN_NAMES[fid], fan=fan, exclusive_group=grp, stackable=stk)
        for fid, fan, grp, stk in raw
    ]


class FanItem(BaseModel):
    id: str
    name: str
    fan: int = 1
    exclusive_group: str | None = None
    stackable: bool = False

    @model_validator(mode="after")
    def _check(self):
        if not _SLUG.match(self.id):
            raise ValueError(f"番种标识「{self.id}」不合法，只能是小写字母/数字/下划线")
        if not self.name.strip():
            raise ValueError("番种名称不能为空")
        if not 0 <= self.fan <= 100:
            raise ValueError(f"番种「{self.name}」的番值必须在 0-100 之间")
        if self.exclusive_group is not None and not self.exclusive_group.strip():
            self.exclusive_group = None
        return self


class TurnTimeout(BaseModel):
    """出牌限时。关闭 = 不限时，牌桌不显示倒计时。"""

    enabled: bool = True
    seconds: int = 15


class KongScore(BaseModel):
    """杠分。关闭 = 仍可杠，但不产生任何分数。"""

    enabled: bool = True
    exposed: int = 1
    hidden: int = 2
    added: int = 1


class ToggleValue(BaseModel):
    """纯开关型规则项（如听牌提示、荒庄罚分）。"""

    enabled: bool = True
    value: int | None = None


class ThirteenUnrelatedOptions(BaseModel):
    """十三不靠各地定义不一，用参数驱动而不是写死。"""

    enabled: bool = False
    require_all_honors: bool = False
    allow_pair: bool = True
    min_gap: int = 3


class PatternSwitches(BaseModel):
    standard: bool = True
    seven_pairs: bool = True
    thirteen_orphans: bool = True
    thirteen_unrelated: ThirteenUnrelatedOptions = Field(
        default_factory=ThirteenUnrelatedOptions
    )


class RuleConfig(BaseModel):
    base_score: int = 1
    fan_mode: Literal["linear", "exponential"] = "exponential"
    fan_cap: int | None = 8
    fan_table: list[FanItem] = Field(default_factory=_default_fan_table)
    patterns: PatternSwitches = Field(default_factory=PatternSwitches)
    allow_chow: bool = True
    turn_timeout: TurnTimeout = Field(default_factory=TurnTimeout)
    kong_score: KongScore = Field(default_factory=KongScore)
    ting_hint: ToggleValue = Field(default_factory=ToggleValue)
    draw_penalty: ToggleValue = Field(
        default_factory=lambda: ToggleValue(enabled=False, value=0)
    )
    discard_pay_mode: Literal["single", "all"] = "single"
    dealer_continue_on_win: bool = True
    dealer_continue_on_draw: bool = True
    rounds_per_game: int = 4
    claim_window_seconds: int = 8

    @model_validator(mode="after")
    def _cross_check(self):
        if not 1 <= self.base_score <= 100:
            raise ValueError("底分必须在 1-100 之间")
        if self.fan_cap is not None and not 0 <= self.fan_cap <= 30:
            raise ValueError("封顶番数必须在 0-30 之间，留空表示不封顶")
        if not 1 <= self.rounds_per_game <= 32:
            raise ValueError("一场局数必须在 1-32 之间")
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

        if self.draw_penalty.enabled:
            penalty = self.draw_penalty.value or 0
            if not 0 <= penalty <= 20:
                raise ValueError("荒庄罚分必须在 0-20 之间")

        patterns = self.patterns
        if not any(
            (
                patterns.standard,
                patterns.seven_pairs,
                patterns.thirteen_orphans,
                patterns.thirteen_unrelated.enabled,
            )
        ):
            raise ValueError("至少要启用一种胡牌牌型，否则这局永远胡不了")

        if patterns.thirteen_unrelated.enabled:
            if not 2 <= patterns.thirteen_unrelated.min_gap <= 9:
                raise ValueError("十三不靠的最小间隔必须在 2-9 之间")
        return self

    # ---- 引擎侧的安全取值（禁止绕过这些方法直接读从属值）----
    def kong_points(self, kind: str) -> int:
        if not self.kong_score.enabled:
            return 0
        if kind == "exposed":
            return self.kong_score.exposed
        if kind == "hidden":
            return self.kong_score.hidden
        if kind == "added":
            return self.kong_score.added
        return 0

    def is_pattern_enabled(self, pattern_id: str) -> bool:
        if pattern_id == "standard":
            return self.patterns.standard
        if pattern_id == "seven_pairs":
            return self.patterns.seven_pairs
        if pattern_id == "thirteen_orphans":
            return self.patterns.thirteen_orphans
        if pattern_id == "thirteen_unrelated":
            return self.patterns.thirteen_unrelated.enabled
        return False

    def fan_of(self, fan_id: str) -> FanItem | None:
        for item in self.fan_table:
            if item.id == fan_id:
                return item
        return None

    def brief(self) -> dict:
        """牌桌顶部与战绩详情用的规则摘要。"""
        return {
            "base_score": self.base_score,
            "fan_mode": self.fan_mode,
            "fan_cap": self.fan_cap,
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
            "ting_hint": self.ting_hint.enabled,
            "patterns": [
                PATTERN_NAMES[key]
                for key in ("standard", "seven_pairs", "thirteen_orphans", "thirteen_unrelated")
                if self.is_pattern_enabled(key)
            ],
            "rounds_per_game": self.rounds_per_game,
        }


class RuleTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    config: RuleConfig


class RuleTemplateCreate(RuleTemplateBase):
    pass


class RuleTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    config: RuleConfig | None = None
    is_active: bool | None = None


class RuleTemplateOut(BaseModel):
    id: int
    owner_id: int | None
    name: str
    description: str
    config: RuleConfig
    is_preset: bool
    is_active: bool
    created_at: str
    updated_at: str


class RuleValidateRequest(BaseModel):
    config: RuleConfig


class RuleValidateResponse(BaseModel):
    ok: bool
    message: str = ""
    summary: str = ""
