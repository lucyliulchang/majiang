"""柏氏规则族 `baishi`（03 §7、细则见 [07-柏氏规则细则](../../../plan/07-柏氏规则细则.md)）。

独立番种/结算/包牌，不复用通用番表，也不复用通用结算：
- 番表 32 项（`baishi/fan.py`，`gang` 只计分不占番）；
- 累计不乘积、不封顶、起胡 1 番；
- 倍数：自摸 ×2、庄家胡全体 ×2、闲家胡庄家份 ×2，三者叠加；
- 包牌：点炮 + ≥3 明牌 + 四种牌型 + 点炮牌属于该牌型 ⇒ 点炮者独付三家之和；
- 杠分 1/2/1 三家各付、抢杠仅明杠、牌尾补牌、海底捞月 100 番；
- 暂停：`switches` 含 `pause`，房态 `paused`（`room.pause`/`room.resume`）。

就绪门禁：`ready` 由 07 §13 自检结果决定（`selfcheck.py`）。用例未全绿前
`ready=false`，开桌返回 `RULE_FAMILY_NOT_READY`；本模块不允许「先用通用番表顶上」。
"""

from game.families.baishi import patterns  # noqa: F401  导入即注册（族内覆盖 4 种牌型）
from game.families.baishi import selfcheck
from game.families.baishi.config import RuleConfig
from game.families.baishi.engine import BaishiEngine, create_engine
from game.families.baishi.presets import PRESETS
from game.families.registry import FamilyPlugin, register_family
from game.tiles import TILE_SET_136

CAPABILITY: dict = {
    "tile_set": TILE_SET_136,
    "allow_chow": True,
    "honors": True,
    "wind_fan": True,
    "patterns": ["standard", "seven_pairs", "thirteen_unrelated", "thirteen_orphans"],
    "fan_combine": ["sum_all"],
    "fan_modes": ["linear"],
    "fan_cap_allowed": False,
    "fan_cap_max": 0,
    "switches": ["turn_timeout", "kong_score", "pause"],
    "settlement": ["self_draw", "discard", "draw", "kong", "rob_kong", "bao_pai"],
    "multi_winner": False,
    "bao_pai": {
        "supported": True,
        "win_type": "discard",
        "min_exposed_melds": 3,
        "patterns": ["qing_yi_se", "hun_yi_se", "quan_zi", "quan_yao"],
        "payer": "discarder_full",
    },
    "dealer_multiplier": {"win": 2, "pay": 2},
    "self_draw_multiplier": 2,
    "lack_suit": False,
    "min_fan_to_win": 1,
    "max_rounds": 4,
}


def build_plugin(pending: tuple[str, ...] | None = None) -> FamilyPlugin:
    """装配族插件；`pending` 为 None 时读 `selfcheck.PENDING_CHECKS`（测试可注入）。"""
    return FamilyPlugin(
        rule_family_code="baishi",
        rule_family_name="柏氏规则",
        engine_code="baishi",
        capability=dict(CAPABILITY),
        config_model=RuleConfig,
        engine_factory=create_engine,
        presets=tuple(PRESETS),
        issues=tuple(selfcheck.gate_issues(pending)),
        sort_order=20,
        memo="累计不乘积、不封顶、包牌独付，细则见 07",
    )


PLUGIN = register_family(build_plugin())

__all__ = [
    "CAPABILITY",
    "BaishiEngine",
    "PLUGIN",
    "PRESETS",
    "RuleConfig",
    "build_plugin",
    "create_engine",
]
