"""规则族注册表：`ruleFamilyCode` → 引擎工厂（03 §2、§9）。

职责：
1. 登记族插件（引擎工厂 + 配置模型 + 能力声明 + 预置模板）；
2. **导入期自检** capability：`patterns` 必须已注册、`tile_set` 必须能建墙、必备字段齐全；
3. 给 `processor/ruleService.py` 提供 `is_ready()`（`ready` 不是数据库列，04 §5）。

自检结果不抛异常、不阻断启动：出问题的族只是 `ready=false`（可列模板、不可开桌），
真正的原因写进 `FamilyPlugin.issues` 并落日志，便于线上排查。

本模块只做静态注册与纯计算：不触库、不读环境变量。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from game.patterns import registered_ids
from game.tiles import new_wall, tile_kinds_of, tile_set_of

logger = logging.getLogger("mahjong.families")

# capability 必备字段（03 §2.2）；缺任意一个即 ready=false
REQUIRED_CAPABILITY_KEYS = (
    "tile_set",
    "allow_chow",
    "honors",
    "wind_fan",
    "patterns",
    "fan_combine",
    "fan_modes",
    "fan_cap_allowed",
    "fan_cap_max",
    "switches",
    "settlement",
    "multi_winner",
    "bao_pai",
    "self_draw_multiplier",
    "dealer_multiplier",
    "lack_suit",
    "min_fan_to_win",
    "max_rounds",
)

KNOWN_SWITCHES = (
    "turn_timeout",
    "kong_score",
    "ting_hint",
    "draw_penalty",
    "pause",
)
KNOWN_SETTLEMENTS = (
    "self_draw",
    "discard",
    "draw",
    "kong",
    "rob_kong",
    "bao_pai",
)
KNOWN_FAN_COMBINE = ("group_best", "sum_all")
KNOWN_FAN_MODES = ("linear", "exponential")


class FamilyError(Exception):
    """规则族不可用（未知族 / 引擎未就绪）。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PresetTemplate:
    """族内预置模板（`familyID=0` / `presetFlag='1'`，只读）。"""

    template_code: str
    template_name: str
    description: str
    config: dict
    sort_order: int = 0


@dataclass(frozen=True)
class FamilyPlugin:
    rule_family_code: str
    rule_family_name: str
    engine_code: str
    capability: dict
    config_model: type
    engine_factory: Callable[..., object]
    presets: tuple[PresetTemplate, ...] = field(default_factory=tuple)
    issues: tuple[str, ...] = ()
    # 落库用元信息（mj_rule_family.sortOrder / memo，03 §2.1）
    sort_order: int = 0
    memo: str = ""

    @property
    def ready(self) -> bool:
        return not self.issues


_REGISTRY: dict[str, FamilyPlugin] = {}


# ---------------------------------------------------------------- 自检


def check_capability(capability: dict, config_model: type | None = None) -> list[str]:
    """按 03 §2.2 自检能力声明，返回问题列表（空 = 通过）。"""
    issues: list[str] = []
    if not isinstance(capability, dict) or not capability:
        return ["capabilityJson 缺失或不是对象"]

    missing = [key for key in REQUIRED_CAPABILITY_KEYS if key not in capability]
    if missing:
        issues.append("capability 缺字段：" + ", ".join(missing))

    tile_set = str(capability.get("tile_set") or "")
    try:
        kinds = tile_kinds_of(tile_set)
        wall = new_wall(None, tile_set)
    except ValueError as error:
        issues.append(f"tile_set 不可建墙：{error}")
    else:
        if len(wall) != kinds * 4 or len(tile_set_of(tile_set)) != kinds:
            issues.append(f"tile_set={tile_set} 建墙张数异常")

    patterns = capability.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        issues.append("capability.patterns 为空")
    else:
        known = set(registered_ids())
        unknown = [item for item in patterns if item not in known]
        if unknown:
            issues.append("牌型未注册：" + ", ".join(unknown))

    for key, allowed in (
        ("switches", KNOWN_SWITCHES),
        ("settlement", KNOWN_SETTLEMENTS),
        ("fan_combine", KNOWN_FAN_COMBINE),
        ("fan_modes", KNOWN_FAN_MODES),
    ):
        values = capability.get(key)
        if not isinstance(values, list) or not values:
            issues.append(f"capability.{key} 为空")
            continue
        bad = [item for item in values if item not in allowed]
        if bad:
            issues.append(f"capability.{key} 含未知取值：" + ", ".join(map(str, bad)))

    dealer = capability.get("dealer_multiplier")
    if not isinstance(dealer, dict) or set(dealer) != {"win", "pay"}:
        issues.append("capability.dealer_multiplier 必须是 {win, pay}")

    max_rounds = capability.get("max_rounds")
    if max_rounds is not None and max_rounds != 4:
        issues.append("capability.max_rounds 必须固定为 4（一圈 4 个庄次）")

    if config_model is not None and not _has_config_defaults(config_model, capability):
        issues.append("配置模型默认值超出族能力（开关/牌型/折算方式）")
    return issues


def _has_config_defaults(config_model: type, capability: dict) -> bool:
    """族配置的默认值必须落在自己的能力声明内，否则新建模板即非法。"""
    try:
        config = config_model()
    except Exception:  # noqa: BLE001 默认值都建不出来，交给上层判失败
        return False

    switches = set(capability.get("switches") or [])
    if getattr(getattr(config, "kong_score", None), "enabled", False) and "kong_score" not in switches:
        return False
    if getattr(getattr(config, "turn_timeout", None), "enabled", False) and "turn_timeout" not in switches:
        return False
    if getattr(getattr(config, "ting_hint", None), "enabled", False) and "ting_hint" not in switches:
        return False
    if getattr(getattr(config, "draw_penalty", None), "enabled", False) and "draw_penalty" not in switches:
        return False

    fan_modes = set(capability.get("fan_modes") or [])
    if getattr(config, "fan_mode", None) not in fan_modes:
        return False
    if getattr(config, "allow_chow", False) and capability.get("allow_chow") is False:
        return False
    if getattr(config, "fan_cap", None) is not None and capability.get("fan_cap_allowed") is False:
        return False
    return True


def register_family(plugin: FamilyPlugin) -> FamilyPlugin:
    """登记族插件并跑导入期自检（同一 code 重复登记以最后一次为准）。"""
    issues = check_capability(plugin.capability, plugin.config_model)
    stored = FamilyPlugin(
        rule_family_code=plugin.rule_family_code,
        rule_family_name=plugin.rule_family_name,
        engine_code=plugin.engine_code,
        capability=dict(plugin.capability),
        config_model=plugin.config_model,
        engine_factory=plugin.engine_factory,
        presets=tuple(plugin.presets),
        issues=tuple(issues),
        sort_order=plugin.sort_order,
        memo=plugin.memo,
    )
    _REGISTRY[stored.rule_family_code] = stored
    if issues:
        logger.warning(
            "规则族自检未通过 %s：%s", stored.rule_family_code, "；".join(issues)
        )
    else:
        logger.info(
            "规则族已注册 %s(engine=%s, patterns=%s)",
            stored.rule_family_code,
            stored.engine_code,
            ",".join(stored.capability.get("patterns") or []),
        )
    return stored


# ---------------------------------------------------------------- 查询


def get_family(rule_family_code: str) -> FamilyPlugin | None:
    return _REGISTRY.get((rule_family_code or "").strip())


def require_family(rule_family_code: str) -> FamilyPlugin:
    plugin = get_family(rule_family_code)
    if plugin is None:
        raise FamilyError("RULE_FAMILY_NOT_FOUND", "规则族不存在")
    return plugin


def registered_codes() -> list[str]:
    return list(_REGISTRY.keys())


def all_families() -> list[FamilyPlugin]:
    return list(_REGISTRY.values())


def capability_of(rule_family_code: str) -> dict:
    plugin = get_family(rule_family_code)
    return dict(plugin.capability) if plugin else {}


def presets_of(rule_family_code: str) -> tuple[PresetTemplate, ...]:
    plugin = get_family(rule_family_code)
    return plugin.presets if plugin else ()


def config_model_of(rule_family_code: str) -> type:
    return require_family(rule_family_code).config_model


def is_ready(rule_family_code: str, capability: dict | None = None) -> tuple[bool, list[str]]:
    """族是否可开桌（04 §5）：引擎已注册 + 自检通过 + 该族 capability 与注册表一致。

    `capability` 传数据库里的 `capabilityJson`：库里若被改出未注册的牌型或未知牌张集合，
    也应拒绝开桌，而不是等到发牌时才炸。
    """
    plugin = get_family(rule_family_code)
    if plugin is None:
        return False, ["引擎未注册"]
    issues = list(plugin.issues)
    if capability:
        issues.extend(check_capability(capability, plugin.config_model))
    return (not issues), issues


def create_engine(rule_family_code: str, rule, seats, **kwargs):
    """按族取引擎工厂。族未注册 → FamilyError（路由层转 400）。"""
    plugin = require_family(rule_family_code)
    if not plugin.ready:
        raise FamilyError("RULE_FAMILY_NOT_READY", "该规则族细则尚未配置完成")
    return plugin.engine_factory(rule, seats, **kwargs)


def load_config(rule_family_code: str, raw: dict):
    """用族的配置模型解析参数（未知字段由模型 `extra=forbid` 拒绝）。"""
    model = config_model_of(rule_family_code)
    return model.model_validate(raw or {})


__all__ = [
    "FamilyError",
    "FamilyPlugin",
    "KNOWN_FAN_COMBINE",
    "KNOWN_FAN_MODES",
    "KNOWN_SETTLEMENTS",
    "KNOWN_SWITCHES",
    "PresetTemplate",
    "REQUIRED_CAPABILITY_KEYS",
    "all_families",
    "capability_of",
    "check_capability",
    "config_model_of",
    "create_engine",
    "get_family",
    "is_ready",
    "load_config",
    "presets_of",
    "register_family",
    "registered_codes",
    "require_family",
]
