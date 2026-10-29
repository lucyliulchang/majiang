"""广东推倒胡 `guangdong` 的规则配置（03 §5）。

首期实现方式：**复用通用引擎 + 广东番表/开关预设**，不新增结算规则，因此这里只做两件事：
1. 换掉默认番表（12 项，鸡胡/碰碰胡/混一色/清一色/七对/龙七对/十三幺/自摸/杠/海底/
   杠上开花/抢杠胡）；
2. 声明 `family_code`，让牌型注册表挑广东可见的插件（无十三不靠）。

其余字段（三组开关、吃牌、点炮付款、局数）与通用族同构，`extra=forbid` 继续生效，
所以广东模板里出现族外字段仍会被 `ruleService` 转成 400。
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from game.families.generic.config import FanItem  # noqa: F401  同一套番种结构
from game.families.generic.config import (
    KongScore,
    PatternSwitches,
    ThirteenUnrelatedOptions,
    ToggleValue,
    TurnTimeout,
)
from game.families.generic.config import RuleConfig as _GenericRuleConfig

#: 广东番表（03 §5）：12 项
GUANGDONG_FAN_NAMES: dict[str, str] = {
    "ji_hu": "鸡胡",
    "peng_peng_hu": "碰碰胡",
    "hun_yi_se": "混一色",
    "qing_yi_se": "清一色",
    "qi_dui": "七对",
    "long_qi_dui": "龙七对",
    "shi_san_yao": "十三幺",
    "zi_mo": "自摸",
    "kong": "杠",
    "hai_di": "海底捞月",
    "gang_shang_hua": "杠上开花",
    "qiang_gang_hu": "抢杠胡",
}

#: 广东封顶候选：4/6/8/10/不封顶（默认 8；`None` = 不封顶）
GUANGDONG_FAN_CAP_CHOICES = (4, 6, 8, 10, None)
GUANGDONG_DEFAULT_FAN_CAP = 8

#: 番种标识（供牌型插件引用，避免魔法字符串散落）
FAN_JI_HU = "ji_hu"


def default_fan_table() -> list[FanItem]:
    """广东 12 项番表；互斥组口径沿用 03 §4.2（同组取最高）。"""
    raw = [
        ("ji_hu", 1, "structure", False),
        ("peng_peng_hu", 3, "structure", False),
        ("hun_yi_se", 3, "suit", False),
        ("qing_yi_se", 6, "suit", False),
        ("qi_dui", 4, "special", False),
        ("long_qi_dui", 8, "special", False),
        ("shi_san_yao", 8, "special", False),
        ("zi_mo", 1, None, False),
        ("kong", 1, None, True),
        ("hai_di", 1, None, False),
        ("gang_shang_hua", 1, None, False),
        ("qiang_gang_hu", 1, None, False),
    ]
    return [
        FanItem(id=fid, name=GUANGDONG_FAN_NAMES[fid], fan=fan, exclusive_group=grp, stackable=stk)
        for fid, fan, grp, stk in raw
    ]


class RuleConfig(_GenericRuleConfig):
    """广东推倒胡参数：通用配置 + 广东番表（封顶默认 8）。"""

    family_code: ClassVar[str] = "guangdong"

    fan_table: list[FanItem] = Field(default_factory=default_fan_table)
    # 广东番值区间窄（1–8），默认线性累加，与预置模板一致
    fan_mode: Literal["linear", "exponential"] = "linear"
    fan_cap: int | None = GUANGDONG_DEFAULT_FAN_CAP


__all__ = [
    "FAN_JI_HU",
    "GUANGDONG_DEFAULT_FAN_CAP",
    "GUANGDONG_FAN_CAP_CHOICES",
    "GUANGDONG_FAN_NAMES",
    "FanItem",
    "KongScore",
    "PatternSwitches",
    "RuleConfig",
    "ThirteenUnrelatedOptions",
    "ToggleValue",
    "TurnTimeout",
    "default_fan_table",
]
