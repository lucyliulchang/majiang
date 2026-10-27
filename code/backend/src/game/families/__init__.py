"""规则族插件目录（03 §3.1）。

导入本包即完成**全部族的注册**（各族 `__init__.py` 末尾调用 `registry.register_family`），
注册表在导入期自检 capability：patterns 已注册、tile_set 可建墙、必备字段齐全。
因此服务端、种子脚本、测试都只需 `import game.families`。

S6 已接入：`generic`（等价迁移基线）、`guangdong`（复用通用骨架）。
`sichuan` / `baishi` 在 S7 接入，未注册即 `ready=false`（可列族与模板、不可开桌）。
"""

from game.families import generic, guangdong  # noqa: F401  导入即注册
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
