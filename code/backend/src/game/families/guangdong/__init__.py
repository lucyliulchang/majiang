"""广东推倒胡 `guangdong`（03 §5）。

实现方式：**复用通用引擎 + 广东番表/开关预设**，不新增结算规则。
与通用族的能力差异：
- `patterns` 去掉 `thirteen_unrelated`（广东无十三不靠）；
- `wind_fan=false`（番表无门风/圈风项）；
- `settlement` 与 `settlement` 能力同 generic（自摸/点炮/荒庄/杠/抢杠）。
"""

from game.families.generic import CAPABILITY as _GENERIC_CAPABILITY
from game.families.guangdong import patterns  # noqa: F401  导入即注册（standard/seven_pairs/thirteen_orphans）
from game.families.guangdong.config import RuleConfig
from game.families.guangdong.engine import GuangdongEngine, create_engine
from game.families.guangdong.presets import PRESETS
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
        presets=PRESETS,
        sort_order=30,
        memo="136 张（含字牌），可吃，广东 12 项番表，封顶 4/6/8/10/不封顶",
    )
)

__all__ = ["CAPABILITY", "GuangdongEngine", "PLUGIN", "PRESETS", "RuleConfig", "create_engine"]
