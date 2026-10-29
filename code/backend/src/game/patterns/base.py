"""牌型插件契约与注册表（跨族共用）。

新增牌型：在 `game/families/{engineCode}/patterns/` 加一个文件，实现 WinPattern 并用
`@register_pattern` 注册，再在该族的 `patterns/__init__.py` 里 import 一下即可，
核心引擎不需要改。

两级注册表（S7）：
- `REGISTRY`：全局默认（`generic` 一族实现，`guangdong` / `sichuan` 直接复用）；
- `FAMILY_REGISTRY[family]`：族内覆盖/新增（`baishi` 用同名 id 覆盖番种求值，
  `sichuan` 用 `long_seven_pairs` 扩展牌型）。

查表规则：`patterns_for(family)` = 全局 ∪ 族内（族内同名 id 覆盖全局），
所以族只需要写差异项，不必把 4 种牌型全抄一遍。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from game.families.generic.config import RuleConfig
    from game.hand import HandContext

#: 未声明家族时的默认家族（骨架自带 4 种牌型的归属）
DEFAULT_FAMILY = "generic"


@dataclass
class FanHit:
    """一个命中的番种。count 允许 >1（例如多个杠）。"""

    id: str
    count: int = 1


@dataclass
class WinResult:
    pattern_id: str
    pattern_name: str
    fan_hits: list[FanHit] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


@runtime_checkable
class WinPattern(Protocol):
    id: str
    name: str

    def match(self, ctx: "HandContext") -> bool: ...

    def calc_fan(self, ctx: "HandContext", rule: "RuleConfig") -> list[FanHit]: ...


REGISTRY: dict[str, WinPattern] = {}
FAMILY_REGISTRY: dict[str, dict[str, WinPattern]] = {}


def register_pattern(cls: type, family: str | None = None) -> type:
    """注册牌型插件；`family` 为空表示全局默认（`generic` 口径）。"""
    instance = cls()
    if not isinstance(instance, WinPattern):
        raise TypeError(f"{cls.__name__} 必须实现 match 与 calc_fan")
    if not family:
        REGISTRY[instance.id] = instance
        return cls
    FAMILY_REGISTRY.setdefault(family, {})[instance.id] = instance
    return cls


def patterns_for(family: str | None = None) -> dict[str, WinPattern]:
    """某族可见的牌型：全局默认 + 族内覆盖（族内同名 id 优先）。"""
    merged = dict(REGISTRY)
    merged.update(FAMILY_REGISTRY.get(family or DEFAULT_FAMILY, {}))
    return merged


def get_pattern(pattern_id: str, family: str | None = None) -> WinPattern | None:
    return patterns_for(family).get(pattern_id)


def registered_ids(family: str | None = None) -> list[str]:
    return list(patterns_for(family).keys())
