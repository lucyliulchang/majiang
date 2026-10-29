"""规则域服务：规则族清单、模板增删改查、复制派生与校验（04 §5、03 §4）。

职责边界（01 §2）：
  - 路由只解析参数、调本模块、套响应模型；
  - 本模块负责权限（成员 / 模板创建者 / 家庭管理员）、族能力校验、事务与错误码；
  - 所有 SQL 都在 `common/mysqlCommon.py` 的手写 query_* / update_* 里。

口径：
  - 全局预置模板 `familyID=0`：登录即可读，任何家庭都能拿来开桌；`presetFlag='1'` 只读；
  - 家庭模板：只有本家庭 ACTIVE 成员可见，创建者或家庭管理员可改/停用；
  - `ready` 是引擎自检值，不是数据库列（02 §3.5）：由 `game/families/registry.py`
    的导入期自检结果拼出（引擎已注册 + capability 可解析 + patterns 已注册 + tile_set 可建墙）；
  - 校验三层（03 §9.3）：字段级（Pydantic）→ 跨字段（model_validator）→ 族能力白名单；
    未知字段一律 400。
"""

from __future__ import annotations

import secrets

from pydantic import ValidationError

from common import miscCommon as misc
from common import mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from game.families import registry
from processor import familyService

logger = get_logger("mahjong.rule")

# 开关类配置项（校验错误归类 + 白名单逐项比对；族不支持的开关一律拒绝）
_SWITCH_KEYS = (
    "turn_timeout",
    "kong_score",
    "ting_hint",
    "draw_penalty",
    "pause",
    "cha_jiao",
    "hua_zhu",
)


class RuleServiceError(BizError):
    """规则域业务异常（HTTP 状态 + 错误码 + 中文提示）。"""


# ---------------------------------------------------------------- 小工具


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _flag(value) -> bool:
    return str(value or "").strip() in ("1", "true", "True")


def _configError(code: str, message: str, httpStatus: int = 400) -> RuleServiceError:
    return RuleServiceError(code, message, httpStatus)


def _iso(ymdhms: str) -> str:
    return misc.ymdhmsToIso(ymdhms)


def isReady(row: dict) -> bool:
    """族是否可开桌：引擎已注册 + 自检通过 + 库里的 capability 与注册表一致（04 §5）。"""
    code = _text(row, "ruleFamilyCode")
    if not code:
        return False
    capability = row.get("capabilityJson")
    ready, issues = registry.is_ready(
        code, capability if isinstance(capability, dict) else None
    )
    if not ready and issues:
        logger.debug("族未就绪 %s：%s", code, "；".join(issues))
    return ready


def ruleFamilyOut(row: dict) -> dict:
    """04 §5 的 rule_family 结构。"""
    capability = row.get("capabilityJson")
    return {
        "rule_family_code": _text(row, "ruleFamilyCode"),
        "rule_family_name": _text(row, "ruleFamilyName"),
        "engine_code": _text(row, "engineCode"),
        "tile_set_code": _text(row, "tileSetCode"),
        "capability": capability if isinstance(capability, dict) else {},
        "status": _text(row, "ruleFamilyStatus") or "ENABLED",
        "sort_order": int(row.get("sortOrder") or 0),
        "ready": isReady(row),
    }


def templateOut(row: dict, familyCode: str | None = None) -> dict:
    """04 §5 的 template 结构；`family_code=None` 表示全局预置（familyID=0）。"""
    familyID = int(row.get("familyID") or 0)
    config = row.get("configJson")
    createdAt = _text(row, "regYMDHMS")
    return {
        "id": int(row.get("recID") or 0),
        "template_code": _text(row, "templateCode"),
        "family_code": None if familyID == 0 else (familyCode or ""),
        "rule_family_code": _text(row, "ruleFamilyCode"),
        "template_name": _text(row, "templateName"),
        "description": _text(row, "description"),
        "config": config if isinstance(config, dict) else {},
        "is_preset": _flag(row.get("presetFlag")),
        "is_active": _flag(row.get("activeFlag")),
        "owner_login_id": _text(row, "ownerLoginID") or None,
        "created_at": _iso(createdAt),
        "updated_at": _iso(_text(row, "modifyYMDHMS") or createdAt),
    }


# ---------------------------------------------------------------- 校验


_FIELD_ERROR_CODE = {
    "base_score": "RULE_BASE_SCORE_INVALID",
    "fan_cap": "RULE_FAN_CAP_INVALID",
    "fan_table": "RULE_FAN_TABLE_INVALID",
    "fan_mode": "RULE_CONFIG_INVALID",
    "patterns": "RULE_PATTERN_EMPTY",
    "turn_timeout": "RULE_TURN_TIMEOUT_INVALID",
    "kong_score": "RULE_KONG_SCORE_INVALID",
    "ting_hint": "RULE_SWITCH_UNSUPPORTED",
    "draw_penalty": "RULE_DRAW_PENALTY_INVALID",
    "rounds_per_game": "RULE_ROUNDS_INVALID",
    "claim_window_seconds": "RULE_CLAIM_WINDOW_INVALID",
    "allow_chow": "RULE_SWITCH_UNSUPPORTED",
}

# 跨字段校验（model_validator）的 loc 为空，只能按中文文案归到细粒度错误码
_MESSAGE_KEYWORD_CODE = (
    ("底分", "RULE_BASE_SCORE_INVALID"),
    ("封顶", "RULE_FAN_CAP_INVALID"),
    ("番表", "RULE_FAN_TABLE_INVALID"),
    ("番种", "RULE_FAN_TABLE_INVALID"),
    ("限时", "RULE_TURN_TIMEOUT_INVALID"),
    ("杠", "RULE_KONG_SCORE_INVALID"),
    ("荒庄", "RULE_DRAW_PENALTY_INVALID"),
    ("局数", "RULE_ROUNDS_INVALID"),
    ("庄次", "RULE_ROUNDS_INVALID"),
    ("响应窗口", "RULE_CLAIM_WINDOW_INVALID"),
    ("询问窗口", "RULE_CLAIM_WINDOW_INVALID"),
    ("牌型", "RULE_PATTERN_EMPTY"),
    ("最小间隔", "RULE_MIN_GAP_INVALID"),
)


def _raiseConfigError(error: ValidationError):
    """把 Pydantic 校验错误映射成 04 §10 的细粒度错误码。"""
    errors = error.errors()
    first = errors[0] if errors else {}
    loc = first.get("loc") or ()
    field = str(loc[0]) if loc else ""
    errorType = str(first.get("type") or "")
    rawMessage = str(first.get("msg") or "规则配置不合法").replace("Value error, ", "")

    if errorType == "extra_forbidden":
        # 未知字段：不暴露 capabilities 之外的任何键名之外的信息，直接 400
        raise _configError(
            "RULE_CONFIG_INVALID", f"当前规则族不支持规则项「{field}」"
        )

    message = rawMessage
    code = _FIELD_ERROR_CODE.get(field, "")
    if not code:
        for keyword, keywordCode in _MESSAGE_KEYWORD_CODE:
            if keyword in message:
                code = keywordCode
                break
    raise _configError(code or "RULE_CONFIG_INVALID", message)


def _enabledPatterns(config) -> list[str]:
    patterns = getattr(config, "patterns", None)
    if patterns is None:
        return []
    enabled: list[str] = []
    if getattr(patterns, "standard", False):
        enabled.append("standard")
    if getattr(patterns, "seven_pairs", False):
        enabled.append("seven_pairs")
    if getattr(patterns, "thirteen_orphans", False):
        enabled.append("thirteen_orphans")
    thirteenUnrelated = getattr(patterns, "thirteen_unrelated", None)
    if thirteenUnrelated is not None and getattr(thirteenUnrelated, "enabled", False):
        enabled.append("thirteen_unrelated")
    if getattr(patterns, "long_seven_pairs", False):
        enabled.append("long_seven_pairs")
    return enabled


def _assertCapability(capability: dict, config, rawConfig: dict) -> None:
    """族能力白名单（03 §2.2 / §4.1）：字段级 + 跨字段之外的第三层校验。"""
    if not capability:
        # 库里 capability 缺失：按「族未就绪」处理，不允许把模板写进半残状态
        raise _configError("RULE_FAMILY_NOT_READY", "该规则族细则尚未配置完成")

    # 1) 开关白名单：配置里出现族不支持的开关即拒绝（无论开关开没开）
    allowedSwitches = set(capability.get("switches") or [])
    for key in _SWITCH_KEYS:
        if key in (rawConfig or {}) and key not in allowedSwitches:
            raise _configError("RULE_SWITCH_UNSUPPORTED", f"当前规则族不支持「{key}」")
    for key in _SWITCH_KEYS:
        section = getattr(config, key, None)
        if section is None:
            continue
        if getattr(section, "enabled", False) and key not in allowedSwitches:
            raise _configError("RULE_SWITCH_UNSUPPORTED", f"当前规则族不支持「{key}」")

    # 2) 牌型白名单
    allowedPatterns = set(capability.get("patterns") or [])
    for patternId in _enabledPatterns(config):
        if patternId not in allowedPatterns:
            raise _configError(
                "RULE_SWITCH_UNSUPPORTED", f"当前规则族不支持牌型「{patternId}」"
            )
    if not allowedPatterns:
        raise _configError("RULE_PATTERN_EMPTY", "至少要启用一种胡牌牌型，否则这局永远胡不了")

    # 3) 吃牌 / 折算方式 / 封顶
    if capability.get("allow_chow") is False and getattr(config, "allow_chow", False):
        raise _configError("RULE_SWITCH_UNSUPPORTED", "当前规则族不支持「可以吃」")

    fanModes = capability.get("fan_modes")
    fanMode = getattr(config, "fan_mode", None)
    if isinstance(fanModes, list) and fanModes and fanMode not in fanModes:
        raise _configError("RULE_SWITCH_UNSUPPORTED", f"当前规则族不支持「{fanMode}」计分方式")

    fanCap = getattr(config, "fan_cap", None)
    if capability.get("fan_cap_allowed") is False and fanCap is not None:
        raise _configError("RULE_FAN_CAP_UNSUPPORTED", "当前规则族不支持封顶")
    capMax = capability.get("fan_cap_max")
    if fanCap is not None and isinstance(capMax, int) and capMax > 0 and fanCap > capMax:
        raise _configError("RULE_FAN_CAP_INVALID", f"封顶番数必须在 0-{capMax} 之间，留空表示不封顶")

    # 4) 字牌相关的牌型在无字牌族里直接禁用
    if capability.get("honors") is False:
        blocked = allowedPatterns & {"thirteen_orphans", "thirteen_unrelated"}
        for patternId in _enabledPatterns(config):
            if patternId in blocked:
                raise _configError(
                    "RULE_SWITCH_UNSUPPORTED", f"当前规则族无字牌，不支持牌型「{patternId}」"
                )


def loadRuleFamily(ruleFamilyCode: str) -> dict:
    """取族（ENABLED）；不存在 → 404 RULE_FAMILY_NOT_FOUND。"""
    code = (ruleFamilyCode or "").strip()
    row = mysqlCommon.query_mj_rule_family_by_code(code) if code else {}
    if not row:
        raise _configError("RULE_FAMILY_NOT_FOUND", "规则族不存在", 404)
    return row


def validateConfig(ruleFamilyCode: str, rawConfig: dict):
    """族存在性 + 字段级 + 跨字段 + 能力白名单，返回校验后的族配置模型。"""
    family = loadRuleFamily(ruleFamilyCode)
    code = _text(family, "ruleFamilyCode")
    try:
        model = registry.config_model_of(code)
    except registry.FamilyError as error:
        # 库里有族、代码里没有引擎：仍然是「族不存在」，不是配置问题
        raise _configError(error.code, error.message, 404 if error.code == "RULE_FAMILY_NOT_FOUND" else 400)
    try:
        config = model.model_validate(rawConfig or {})
    except ValidationError as error:
        _raiseConfigError(error)
    capability = family.get("capabilityJson")
    _assertCapability(capability if isinstance(capability, dict) else {}, config, rawConfig or {})
    return config


def buildSnapshot(templateRow: dict, familyRow: dict, config) -> dict:
    """规则快照（03 §11）：开桌/开局各写一份，内容**不可变**。

    只增字段不删字段：`template_id` 是 S5 已落的键，保留；
    `engine_code` / `capability` / `captured_ymdhms` 为 03 §11 新增键。
    """
    capability = familyRow.get("capabilityJson")
    return {
        "rule_family_code": _text(templateRow, "ruleFamilyCode"),
        "engine_code": _text(familyRow, "engineCode") or _text(templateRow, "ruleFamilyCode"),
        "template_id": int(templateRow.get("recID") or 0),
        "template_code": _text(templateRow, "templateCode"),
        "template_name": _text(templateRow, "templateName"),
        "config": config.model_dump(),
        "capability": dict(capability) if isinstance(capability, dict) else {},
        "captured_ymdhms": misc.getTime(),
        # 开桌时冻结的生效选项：开关关闭时只留 enabled（03 §10 纪律 2）
        "options": _snapshotOptions(config),
    }


def _snapshotOptions(config) -> dict:
    options: dict = {
        "rounds_per_game": getattr(config, "rounds_per_game", 4),
        "claim_window_seconds": getattr(config, "claim_window_seconds", 8),
        "allow_chow": bool(getattr(config, "allow_chow", True)),
    }
    for key in ("turn_timeout", "kong_score", "ting_hint", "draw_penalty", "pause", "cha_jiao", "hua_zhu"):
        section = getattr(config, key, None)
        if section is None:
            continue
        if not getattr(section, "enabled", False):
            options[key] = {"enabled": False}
            continue
        payload = {"enabled": True}
        for attr in ("seconds", "exposed", "hidden", "added", "value", "pay_mode"):
            value = getattr(section, attr, None)
            if value is not None:
                payload[attr] = value
        options[key] = payload
    # 族扩展项（仅在该族配置里存在时才冻结，S7）
    for key in ("multi_winner", "min_fan_to_win", "self_draw_multiplier"):
        value = getattr(config, key, None)
        if value is not None:
            options[key] = value
    dealer = getattr(config, "dealer_rule", None)
    if dealer is not None:
        options["dealer_multiplier"] = {
            "win": int(getattr(dealer, "win_multiplier", 1)),
            "pay": int(getattr(dealer, "pay_multiplier", 1)),
        }
    bao = getattr(config, "bao_pai", None)
    if bao is not None:
        options["bao_pai"] = {
            "enabled": bool(getattr(bao, "enabled", False)),
            "win_type": getattr(bao, "win_type", "discard"),
            "min_exposed_melds": int(getattr(bao, "min_exposed_melds", 3)),
            "patterns": list(getattr(bao, "patterns", []) or []),
            "payer": getattr(bao, "payer", "discarder_full"),
        }
    return options


def summaryText(config) -> str:
    """一句话摘要（04 §5 validate 的 summary）。

    族配置形状不同（柏氏没有 ting_hint、多了倍数/包牌/暂停、不封顶），
    这里统一按 getattr 取，缺什么就不说，避免为每个族写一份摘要。
    """
    fanMode = getattr(config, "fan_mode", "linear")
    parts = [
        f"底分 {getattr(config, 'base_score', 1)}",
        "2 的 N 次方" if fanMode == "exponential" else "线性累加",
    ]
    fanCap = getattr(config, "fan_cap", None)
    if fanCap is not None:
        parts.append(f"封顶 {fanCap} 番")
    elif getattr(config, "fan_cap", "missing") is None:
        parts.append("不封顶")
    parts.append("可以吃" if getattr(config, "allow_chow", True) else "不能吃")

    turnTimeout = getattr(config, "turn_timeout", None)
    if turnTimeout is not None and getattr(turnTimeout, "enabled", False):
        parts.append(f"限时 {turnTimeout.seconds} 秒")
    else:
        parts.append("不限时")

    kongScore = getattr(config, "kong_score", None)
    if kongScore is not None and getattr(kongScore, "enabled", False):
        parts.append(
            f"杠分 明{kongScore.exposed}/暗{kongScore.hidden}/补{kongScore.added}"
        )
    else:
        parts.append("杠不计分")

    tingHint = getattr(config, "ting_hint", None)
    if tingHint is not None:
        parts.append("听牌提示开" if tingHint.enabled else "无听牌提示")

    minFan = getattr(config, "min_fan_to_win", None)
    if minFan:
        parts.append(f"起胡 {minFan} 番")
    if getattr(config, "multi_winner", False):
        parts.append("一家胡了继续打")
    selfDraw = int(getattr(config, "self_draw_multiplier", 1) or 1)
    if selfDraw > 1:
        parts.append(f"自摸 ×{selfDraw}")
    dealer = getattr(config, "dealer_rule", None)
    if dealer is not None:
        parts.append(
            f"庄家 ×{int(getattr(dealer, 'win_multiplier', 1))}/×{int(getattr(dealer, 'pay_multiplier', 1))}"
        )
    bao = getattr(config, "bao_pai", None)
    if bao is not None and getattr(bao, "enabled", False):
        parts.append(f"包牌 ≥{int(getattr(bao, 'min_exposed_melds', 3))} 明牌")
    pause = getattr(config, "pause", None)
    if pause is not None and getattr(pause, "enabled", False):
        parts.append("可暂停")
    return " · ".join(parts)


# ---------------------------------------------------------------- 权限


def _assertVisible(loginID: str, row: dict) -> dict:
    """模板可见性：全局预置放行；家庭模板要求 ACTIVE 成员（返回家庭上下文）。"""
    familyID = int(row.get("familyID") or 0)
    if familyID == 0:
        return {}
    return familyService.assertMemberOfFamilyID(loginID, familyID, requireEnabled=True)


def _assertEditable(loginID: str, row: dict) -> dict:
    """可改/可停用：非预置 + （创建者 或 家庭管理员）。"""
    if _flag(row.get("presetFlag")):
        raise _configError("BAD_REQUEST", "预置模板不能直接改，请先复制一份")
    context = _assertVisible(loginID, row)
    if _text(row, "ownerLoginID") == loginID:
        return context
    if context.get("memberRole") in (familyService.ROLE_OWNER, familyService.ROLE_ADMIN):
        return context
    raise _configError("FORBIDDEN", "这套规则不是你的", 403)


def _loadTemplate(templateID: int) -> dict:
    row = mysqlCommon.query_mj_rule_template_by_id(templateID)
    if not row:
        raise _configError("TEMPLATE_NOT_FOUND", "规则模板不存在", 404)
    return row


# ---------------------------------------------------------------- 规则族


def listRuleFamilies(loginID: str) -> list[dict]:
    """规则族清单：登录即可读（04 §5 #17）。"""
    rows = mysqlCommon.query_mj_rule_family_list()
    return [ruleFamilyOut(row) for row in rows]


# ---------------------------------------------------------------- 模板


def listTemplates(
    loginID: str,
    familyID: int,
    familyCode: str,
    ruleFamilyCode: str = "",
) -> list[dict]:
    """本家庭模板 + 全局预置（04 §5 #18）；只列启用项（LIMIT 由查询函数统一收口）。"""
    familyService.assertMemberOfFamilyID(loginID, familyID, requireEnabled=True)
    rows = mysqlCommon.query_mj_rule_template_list(familyID, ruleFamilyCode)
    return [templateOut(row, familyCode) for row in rows]


def getTemplate(loginID: str, templateID: int) -> dict:
    """模板详情：家庭成员或全局预置（04 §5 #20）。"""
    row = _loadTemplate(templateID)
    context = _assertVisible(loginID, row)
    return templateOut(row, context.get("familyCode", ""))


def _newTemplateCode(ruleFamilyCode: str) -> str:
    """模板编码（幂等键）：族编码 + 随机后缀，长度 ≤ 32。"""
    prefix = "".join(
        char for char in (ruleFamilyCode or "tpl").lower() if char.isalnum() or char == "_"
    )[:20]
    return f"{prefix}_{secrets.token_hex(4)}"


def createTemplate(
    loginID: str,
    familyID: int,
    familyCode: str,
    ruleFamilyCode: str,
    templateName: str,
    description: str,
    rawConfig: dict,
) -> dict:
    """新建家庭模板（04 §5 #19）；预置模板只由种子写入，接口不产生 presetFlag='1'。"""
    familyService.assertMemberOfFamilyID(loginID, familyID, requireEnabled=True)
    family = loadRuleFamily(ruleFamilyCode)
    config = validateConfig(_text(family, "ruleFamilyCode"), rawConfig)
    name = (templateName or "").strip()
    if not name:
        raise _configError("BAD_REQUEST", "模板名称不能为空")

    now = misc.getTime()
    dataSet = {
        "templateCode": _newTemplateCode(ruleFamilyCode),
        "familyID": familyID,
        "ruleFamilyCode": _text(family, "ruleFamilyCode"),
        "templateName": name[:64],
        "description": (description or "").strip()[:400],
        "configJson": config.model_dump(),
        "presetFlag": "0",
        "ownerLoginID": loginID,
        "activeFlag": "1",
        "sortOrder": mysqlCommon.query_mj_rule_template_next_sort(familyID, ruleFamilyCode),
        "regID": loginID,
        "regYMDHMS": now,
        "delFlag": "0",
    }
    recID = 0
    with mysqlCommon.transaction():
        recID = mysqlCommon.insert_mj_rule_template(
            mysqlCommon.MJ_RULE_TEMPLATE_TABLE, dataSet
        )
        if recID <= 0:
            raise RuleServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
    logger.info("模板创建 login=%s family=%s code=%s", loginID, familyCode, dataSet["templateCode"])
    return templateOut(_loadTemplate(recID), familyCode)


def updateTemplate(
    loginID: str,
    templateID: int,
    templateName: str | None = None,
    description: str | None = None,
    rawConfig: dict | None = None,
    activeFlag: bool | None = None,
) -> dict:
    """改模板（04 §5 #21）：创建者或家庭管理员；预置模板 400。"""
    row = _loadTemplate(templateID)
    context = _assertEditable(loginID, row)
    dataSet: dict = {}
    if templateName is not None:
        name = templateName.strip()
        if not name:
            raise _configError("BAD_REQUEST", "模板名称不能为空")
        dataSet["templateName"] = name[:64]
    if description is not None:
        dataSet["description"] = description.strip()[:400]
    if rawConfig is not None:
        config = validateConfig(_text(row, "ruleFamilyCode"), rawConfig)
        dataSet["configJson"] = config.model_dump()
    if activeFlag is not None:
        dataSet["activeFlag"] = "1" if activeFlag else "0"
    if dataSet:
        affected = mysqlCommon.update_mj_rule_template_fields(templateID, dataSet, loginID)
        if affected < 0:
            raise RuleServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
    return templateOut(_loadTemplate(templateID), context.get("familyCode", ""))


def duplicateTemplate(
    loginID: str,
    templateID: int,
    familyID: int,
    familyCode: str,
    templateName: str | None = None,
) -> dict:
    """复制一份到本家庭（04 §5 #22）：预置模板改不动，但可以复制后编辑。"""
    familyService.assertMemberOfFamilyID(loginID, familyID, requireEnabled=True)
    source = _loadTemplate(templateID)
    _assertVisible(loginID, source)
    name = (templateName or f"{_text(source, 'templateName')} 副本").strip()[:64]
    # 复制也要按目标族的能力复核一次：库里残留的旧配置可能已不符合当前能力声明
    config = validateConfig(
        _text(source, "ruleFamilyCode"), source.get("configJson") or {}
    )
    now = misc.getTime()
    dataSet = {
        "templateCode": _newTemplateCode(_text(source, "ruleFamilyCode")),
        "familyID": familyID,
        "ruleFamilyCode": _text(source, "ruleFamilyCode"),
        "templateName": name,
        "description": _text(source, "description")[:400],
        "configJson": config.model_dump(),
        "presetFlag": "0",
        "ownerLoginID": loginID,
        "activeFlag": "1",
        "sortOrder": mysqlCommon.query_mj_rule_template_next_sort(
            familyID, _text(source, "ruleFamilyCode")
        ),
        "regID": loginID,
        "regYMDHMS": now,
        "delFlag": "0",
    }
    recID = 0
    with mysqlCommon.transaction():
        recID = mysqlCommon.insert_mj_rule_template(
            mysqlCommon.MJ_RULE_TEMPLATE_TABLE, dataSet
        )
        if recID <= 0:
            raise RuleServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
    return templateOut(_loadTemplate(recID), familyCode)


def deactivateTemplate(loginID: str, templateID: int) -> dict:
    """停用模板（04 §5 #23）：软态（activeFlag=0），房间快照不受影响。"""
    row = _loadTemplate(templateID)
    context = _assertEditable(loginID, row)
    affected = mysqlCommon.update_mj_rule_template_fields(
        templateID, {"activeFlag": "0"}, loginID
    )
    if affected < 0:
        raise RuleServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
    return templateOut(_loadTemplate(templateID), context.get("familyCode", ""))


def openableTemplate(loginID: str, familyID: int, templateID: int) -> tuple[dict, object, dict]:
    """开桌用：模板必须是本家庭可见、启用、族已就绪（04 §6）。

    返回 `(模板行, 强校验后的族配置, 规则快照)`；失败抛 404/400，**不写任何表**。
    快照在这里生成一次，随后原样写进 `mj_room` 与 `mj_game`（03 §11：两者不可变）。
    """
    row = mysqlCommon.query_mj_rule_template_by_id(templateID)
    if not row:
        raise _configError("TEMPLATE_NOT_FOUND", "规则模板不存在", 404)
    if int(row.get("familyID") or 0) not in (0, int(familyID)):
        # 兄弟家庭的模板不对外暴露存在性
        raise _configError("TEMPLATE_NOT_FOUND", "规则模板不存在", 404)
    if not _flag(row.get("activeFlag")):
        raise _configError("TEMPLATE_NOT_FOUND", "规则模板不存在", 404)
    family = loadRuleFamily(_text(row, "ruleFamilyCode"))
    if not isReady(family):
        raise _configError("RULE_FAMILY_NOT_READY", "该规则族细则尚未配置完成")
    config = validateConfig(
        _text(row, "ruleFamilyCode"), row.get("configJson") or {}
    )
    snapshot = buildSnapshot(row, family, config)
    return row, config, snapshot
