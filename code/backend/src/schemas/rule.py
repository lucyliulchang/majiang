"""规则族与模板的协议模型（04 §5）。

族内参数模型（`RuleConfig` 及其子模型）已迁到 `game/families/generic/config.py`
（03 §3.1：族的配置属于插件，不属于协议层）；这里只做**再导出**，
历史 `from schemas.rule import RuleConfig` 全部继续可用。

三组可选规则项（出牌超时 / 杠分 / 听牌提示）统一采用「enabled + 从属值」模型：
- enabled=True 时才校验从属值范围
- enabled=False 时既不校验也不取用，但保留原值，方便来回切换
绝不用 0 / null / -1 表示"未启用"。
"""

from pydantic import BaseModel, Field

# 族配置模型再导出：调用方不必关心它落在哪个族插件目录
from game.families.generic.config import (  # noqa: F401
    FAN_NAMES,
    LEGACY_KEYS,
    PATTERN_NAMES,
    ROUNDS_PER_GAME,
    FanItem,
    KongScore,
    PatternSwitches,
    RuleConfig,
    ThirteenUnrelatedOptions,
    ToggleValue,
    TurnTimeout,
    default_fan_table,
    strip_legacy_keys,
)

class RuleFamilyOut(BaseModel):
    """04 §5 的 rule_family；`ready` 是引擎自检值，不是数据库列。"""

    rule_family_code: str
    rule_family_name: str
    engine_code: str
    tile_set_code: str
    capability: dict = Field(default_factory=dict)
    status: str = "ENABLED"
    sort_order: int = 0
    ready: bool = False


class RuleTemplateCreateRequest(BaseModel):
    """04 §5 #19。config 用 dict 接收：校验失败要回 RULE_CONFIG_INVALID，而不是 FastAPI 422。"""

    family_code: str = ""
    rule_family_code: str = Field(min_length=1, max_length=32)
    template_name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=400)
    config: dict = Field(default_factory=dict)


class RuleTemplateUpdateRequest(BaseModel):
    template_name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=400)
    config: dict | None = None
    active_flag: bool | None = None


class RuleTemplateDuplicateRequest(BaseModel):
    family_code: str = ""
    template_name: str | None = Field(default=None, max_length=64)


class RuleTemplateOut(BaseModel):
    id: int
    template_code: str
    family_code: str | None = None
    rule_family_code: str
    template_name: str
    description: str = ""
    config: dict = Field(default_factory=dict)
    is_preset: bool = False
    is_active: bool = True
    owner_login_id: str | None = None
    created_at: str = ""
    updated_at: str = ""


class RuleValidateRequest(BaseModel):
    rule_family_code: str = "generic"
    config: dict = Field(default_factory=dict)


class RuleValidateResponse(BaseModel):
    ok: bool
    code: str = "OK"
    message: str = ""
    summary: str = ""


__all__ = [
    "FAN_NAMES",
    "LEGACY_KEYS",
    "PATTERN_NAMES",
    "ROUNDS_PER_GAME",
    "FanItem",
    "KongScore",
    "PatternSwitches",
    "RuleConfig",
    "RuleFamilyOut",
    "RuleTemplateCreateRequest",
    "RuleTemplateDuplicateRequest",
    "RuleTemplateOut",
    "RuleTemplateUpdateRequest",
    "RuleValidateRequest",
    "RuleValidateResponse",
    "ThirteenUnrelatedOptions",
    "ToggleValue",
    "TurnTimeout",
    "default_fan_table",
    "strip_legacy_keys",
]
