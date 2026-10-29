"""四川血战到底 `sichuan` 的规则配置（03 §6）。

族扩展字段（仅在 capability 声明支持时才允许出现，03 §4.1）：

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `lack_suit_required` | `True` | 缺一门：胡牌时手牌 + 副露只能有两种花色；四川固定为开，不允许关 |
| `multi_winner` | `True` | 血战到底：一家胡牌即退出，其余继续，直到 3 人胡或牌墙耗尽 |
| `min_fan_to_win` | `0` | 起胡番数（可配） |
| `cha_jiao` / `hua_zhu` | `{enabled: false}` | 查叫 / 查花猪：**默认关**，细则未细化前不允许开启（见遗留问题） |

牌张 108（万筒条各 36，无字牌）、禁吃、杠分为刮风（明杠，放杠者付）/ 下雨（暗杠，
三家各付）。
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, model_validator

from game.families.generic.config import FanItem
from game.families.generic.config import KongScore as _KongScore
from game.families.generic.config import PatternSwitches as _PatternSwitches
from game.families.generic.config import RuleConfig as _GenericRuleConfig
from game.families.generic.config import ToggleValue, TurnTimeout

#: 四川番表（03 §8「四川番表（待细化）」的默认实现，见遗留问题）
SICHUAN_FAN_NAMES: dict[str, str] = {
    "ping_hu": "平胡",
    "peng_peng_hu": "碰碰胡",
    "qing_yi_se": "清一色",
    "hun_yi_se": "混一色",
    "qi_dui": "七对",
    "long_qi_dui": "龙七对",
    "zi_mo": "自摸",
    "men_qian": "门清",
    "kong": "杠",
    "hai_di": "海底捞月",
    "gang_shang_hua": "杠上开花",
    "qiang_gang_hu": "抢杠胡",
}

DEFAULT_FAN_CAP = 8


def default_fan_table() -> list[FanItem]:
    raw = [
        ("ping_hu", 1, "structure", False),
        ("peng_peng_hu", 2, "structure", False),
        ("qing_yi_se", 6, "suit", False),
        ("hun_yi_se", 2, "suit", False),
        ("qi_dui", 4, "special", False),
        ("long_qi_dui", 8, "special", False),
        ("zi_mo", 1, None, False),
        ("men_qian", 1, None, False),
        ("kong", 1, None, True),
        ("hai_di", 1, None, False),
        ("gang_shang_hua", 1, None, False),
        ("qiang_gang_hu", 1, None, False),
    ]
    return [
        FanItem(id=fid, name=SICHUAN_FAN_NAMES[fid], fan=fan, exclusive_group=grp, stackable=stk)
        for fid, fan, grp, stk in raw
    ]


class PatternSwitches(_PatternSwitches):
    """四川牌型：标准胡 / 七对 / 龙七对；无十三幺、无十三不靠（03 §6）。

    十三幺在无字牌族里恒关；十三不靠沿用通用结构但恒为关闭，且不出现在 capability 里
    （`ruleService` 的第二层白名单会直接拒绝开启）。
    """

    long_seven_pairs: bool = True
    thirteen_orphans: bool = False


class KongScore(_KongScore):
    """刮风（明杠）/ 下雨（暗杠）；付款方口径沿用通用族（明杠放杠者付，暗杠三家各付）。"""


class SichuanRuleConfig(_GenericRuleConfig):
    family_code: ClassVar[str] = "sichuan"

    fan_table: list[FanItem] = Field(default_factory=default_fan_table)
    fan_mode: Literal["linear", "exponential"] = "linear"
    fan_cap: int | None = DEFAULT_FAN_CAP
    patterns: PatternSwitches = Field(default_factory=PatternSwitches)
    allow_chow: bool = False
    lack_suit_required: bool = True
    multi_winner: bool = True
    min_fan_to_win: int = 0
    cha_jiao: ToggleValue = Field(default_factory=lambda: ToggleValue(enabled=False, value=0))
    hua_zhu: ToggleValue = Field(default_factory=lambda: ToggleValue(enabled=False, value=0))

    @model_validator(mode="after")
    def _sichuan_check(self):
        if self.allow_chow:
            raise ValueError("四川麻将不能吃牌，allow_chow 必须为 false")
        if not self.lack_suit_required:
            raise ValueError("四川麻将必须缺一门才能胡，lack_suit_required 不能关闭")
        if not 0 <= self.min_fan_to_win <= 100:
            raise ValueError("起胡番数必须在 0-100 之间")
        if self.cha_jiao.enabled or self.hua_zhu.enabled:
            raise ValueError("四川查叫/查花猪细则尚未细化，暂不能开启")
        if not (self.patterns.standard or self.patterns.seven_pairs or self.patterns.long_seven_pairs):
            raise ValueError("至少要启用一种胡牌牌型，否则这局永远胡不了")
        return self

    def is_pattern_enabled(self, pattern_id: str) -> bool:
        if pattern_id == "long_seven_pairs":
            return bool(self.patterns.long_seven_pairs)
        if pattern_id in ("thirteen_orphans", "thirteen_unrelated"):
            return False
        return super().is_pattern_enabled(pattern_id)


#: 对外统一名字（族注册表按 `config_model` 取用）
RuleConfig = SichuanRuleConfig


__all__ = [
    "DEFAULT_FAN_CAP",
    "FanItem",
    "KongScore",
    "PatternSwitches",
    "RuleConfig",
    "SICHUAN_FAN_NAMES",
    "SichuanRuleConfig",
    "ToggleValue",
    "TurnTimeout",
    "default_fan_table",
]
