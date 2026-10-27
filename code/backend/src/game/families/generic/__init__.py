"""通用家庭标准族 `generic`（03 §4）。

完整复刻 S6 之前的单一 `RuleConfig` 语义，作为规则族改造的回归基线：
- 能力声明 `CAPABILITY`（03 §2.2 逐字段）；
- 配置模型 `RuleConfig`（20 番种 / 四牌型 / 三组开关 / 结算字段）；
- 牌型插件 `patterns/`（standard / seven_pairs / thirteen_orphans / thirteen_unrelated）；
- 引擎 `engine.py`（适配通用骨架）+ 4 套预置模板 `presets.py`。
"""

from game.families.generic import patterns  # noqa: F401  导入即注册牌型（自检依赖）
from game.families.generic.config import ROUNDS_PER_GAME, RuleConfig
from game.families.generic.engine import GenericEngine, create_engine
from game.families.generic.presets import PRESETS
from game.families.registry import FamilyPlugin, register_family
from game.tiles import TILE_SET_136

# 能力声明（03 §2.2）：只增不改语义，新增字段必须有默认值
CAPABILITY: dict = {
    "tile_set": TILE_SET_136,
    "allow_chow": True,
    "honors": True,
    "wind_fan": True,
    "patterns": ["standard", "seven_pairs", "thirteen_orphans", "thirteen_unrelated"],
    "fan_combine": ["group_best"],
    "fan_modes": ["linear", "exponential"],
    "fan_cap_allowed": True,
    "fan_cap_max": 30,
    "switches": ["turn_timeout", "kong_score", "ting_hint", "draw_penalty"],
    "settlement": ["self_draw", "discard", "draw", "kong", "rob_kong"],
    "multi_winner": False,
    "bao_pai": False,
    "self_draw_multiplier": 1,
    "dealer_multiplier": {"win": 1, "pay": 1},
    "lack_suit": False,
    "min_fan_to_win": 0,
    "max_rounds": ROUNDS_PER_GAME,
}

PLUGIN = register_family(
    FamilyPlugin(
        rule_family_code="generic",
        rule_family_name="通用家庭标准",
        engine_code="generic",
        capability=CAPABILITY,
        config_model=RuleConfig,
        engine_factory=create_engine,
        presets=PRESETS,
        sort_order=10,
        memo="完整复刻现有 RuleConfig 语义，作为回归基线",
    )
)

__all__ = ["CAPABILITY", "GenericEngine", "PLUGIN", "PRESETS", "RuleConfig", "create_engine"]
