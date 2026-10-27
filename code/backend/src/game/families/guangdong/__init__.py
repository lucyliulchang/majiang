"""广东推倒胡 `guangdong`（03 §5 首期骨架）。

与通用族的能力差异：`wind_fan=false`（番表无门风/圈风项）、`patterns` 去掉
`thirteen_unrelated`。番表细化与预置模板在 S7 落地。
"""

from game.families.generic import CAPABILITY as _GENERIC_CAPABILITY
from game.families.guangdong.config import RuleConfig
from game.families.guangdong.engine import GuangdongEngine, create_engine
from game.families.registry import FamilyPlugin, register_family
from game.tiles import TILE_SET_136

CAPABILITY: dict = {
    **_GENERIC_CAPABILITY,
    "tile_set": TILE_SET_136,
    "wind_fan": False,
    "patterns": ["standard", "seven_pairs", "thirteen_orphans"],
}

PLUGIN = register_family(
    FamilyPlugin(
        rule_family_code="guangdong",
        rule_family_name="广东推倒胡",
        engine_code="guangdong",
        capability=CAPABILITY,
        config_model=RuleConfig,
        engine_factory=create_engine,
        presets=(),
        sort_order=30,
        memo="136 张（含字牌），可吃，简化番表",
    )
)

__all__ = ["CAPABILITY", "GuangdongEngine", "PLUGIN", "RuleConfig", "create_engine"]
