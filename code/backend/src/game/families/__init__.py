"""规则族插件目录（03 §3.1）。

导入本包即完成**全部族的注册**（各族 `__init__.py` 末尾调用 `registry.register_family`），
注册表在导入期自检 capability：patterns 已注册、tile_set 可建墙、必备字段齐全。

S6 接入：`generic`（等价迁移基线）、`guangdong`（复用通用骨架）。
S7 接入：`sichuan`（108 张 / 禁吃 / 缺一门 / 多赢家）、`baishi`（34 项番表 / 包牌 /
倍数 / 暂停，`ready` 由 07 §13 自检结果决定）。
"""

from game.families import generic, guangdong, sichuan, baishi  # noqa: F401  导入即注册
from game.families.registry import (  # noqa: F401  对外统一出口
    FamilyError,
    FamilyPlugin,
    PresetTemplate,
    all_families,
    capability_of,
    create_engine,
    get_family,
    is_ready,
    load_config,
    presets_of,
    register_family,
    registered_codes,
    require_family,
)

__all__ = [
    "FamilyError",
    "FamilyPlugin",
    "PresetTemplate",
    "all_families",
    "capability_of",
    "create_engine",
    "get_family",
    "is_ready",
    "load_config",
    "presets_of",
    "register_family",
    "registered_codes",
    "require_family",
]
