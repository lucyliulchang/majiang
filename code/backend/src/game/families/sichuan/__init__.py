"""四川血战到底 `sichuan`（03 §6）。

实现方式：通用骨架 + 四川引擎（108 张、禁吃、缺一门、多赢家）。
- 牌张：108（万筒条各 36，无字牌），字牌 27–33 不进牌墙、也不接受出牌；
- 吃牌：capability `allow_chow=false`，模板强制 `allow_chow=false`；
- 缺一门：胡牌时手牌 + 副露只能有两种花色（`lack_suit_required`）；
- 血战到底：一家胡牌即退出，其余继续，直到 3 人胡或牌墙耗尽（`multi_winner`）；
- 杠分：刮风（明杠，放杠者付）/ 下雨（暗杠，三家各付）/ 补杠；
- 查叫、查花猪：只有开关与结算钩子，默认关，细则未细化前不允许开启（见遗留问题）。
"""

from game.families.registry import FamilyPlugin, register_family
from game.families.sichuan import patterns  # noqa: F401  导入即注册（long_seven_pairs）
from game.families.sichuan.config import RuleConfig
from game.families.sichuan.engine import SichuanEngine, create_engine
from game.families.sichuan.presets import PRESETS
from game.tiles import TILE_SET_108

CAPABILITY: dict = {
    "tile_set": TILE_SET_108,
    "allow_chow": False,
    "honors": False,
    "wind_fan": False,
    # 无字牌：十三幺/十三不靠既不在能力里，也不会被注册到本族
    "patterns": ["standard", "seven_pairs", "long_seven_pairs"],
    "fan_combine": ["group_best"],
    "fan_modes": ["linear", "exponential"],
    "fan_cap_allowed": True,
    "fan_cap_max": 30,
    "switches": ["turn_timeout", "kong_score", "ting_hint", "draw_penalty", "cha_jiao", "hua_zhu"],
    "settlement": ["self_draw", "discard", "draw", "kong", "rob_kong"],
    "multi_winner": True,
    "bao_pai": False,
    "self_draw_multiplier": 1,
    "dealer_multiplier": {"win": 1, "pay": 1},
    "lack_suit": True,
    "min_fan_to_win": 0,
    "max_rounds": 4,
}

PLUGIN = register_family(
    FamilyPlugin(
        rule_family_code="sichuan",
        rule_family_name="四川血战到底",
        engine_code="sichuan",
        capability=CAPABILITY,
        config_model=RuleConfig,
        engine_factory=create_engine,
        presets=PRESETS,
        sort_order=40,
        memo="108 张（无字牌），禁吃，缺一门，多赢家（血战到底）",
    )
)

__all__ = ["CAPABILITY", "PLUGIN", "PRESETS", "RuleConfig", "SichuanEngine", "create_engine"]
