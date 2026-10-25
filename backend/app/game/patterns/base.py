"""牌型插件契约与注册表。

新增牌型：在本目录加一个文件，实现 WinPattern 并用 @register_pattern 注册，
再在 __init__.py 里 import 一下即可，核心引擎不需要改。
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.game.hand import HandContext
from app.schemas.rule import RuleConfig


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

    def match(self, ctx: HandContext) -> bool: ...

    def calc_fan(self, ctx: HandContext, rule: RuleConfig) -> list[FanHit]: ...


REGISTRY: dict[str, WinPattern] = {}


def register_pattern(cls: type) -> type:
    instance = cls()
    if not isinstance(instance, WinPattern):
        raise TypeError(f"{cls.__name__} 必须实现 match 与 calc_fan")
    REGISTRY[instance.id] = instance
    return cls


def get_pattern(pattern_id: str) -> WinPattern | None:
    return REGISTRY.get(pattern_id)


def registered_ids() -> list[str]:
    return list(REGISTRY.keys())
