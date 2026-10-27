"""通用族牌型插件：standard / seven_pairs / thirteen_orphans / thirteen_unrelated。

迁自 `game/patterns/`（S6）：牌型判定逻辑逐字保留，只改导入路径与类型注解来源。
导入本包即完成注册；`game.families.registry` 在导入期自检 capability 的 patterns 是否都已注册。
"""

from game.families.generic.patterns import (  # noqa: F401  导入即注册
    seven_pairs,
    standard,
    thirteen_orphans,
    thirteen_unrelated,
)

__all__ = ["standard", "seven_pairs", "thirteen_orphans", "thirteen_unrelated"]
