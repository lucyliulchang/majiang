"""规则域服务：规则族清单、模板增删改查、复制派生与校验（04 §5、03 §4）。

职责边界（01 §2）：
  - 路由只解析参数、调本模块、套响应模型；
  - 本模块负责权限（成员 / 模板创建者 / 家庭管理员）、族能力校验、事务与错误码；
  - 所有 SQL 都在 `common/mysqlCommon.py` 的手写 query_* / update_* 里。

口径：
  - 全局预置模板 `familyID=0`：登录即可读，任何家庭都能拿来开桌；`presetFlag='1'` 只读；
  - 家庭模板：只有本家庭 ACTIVE 成员可见，创建者或家庭管理员可改/停用；
  - `ready` 是引擎自检值，不是数据库列（02 §3.5）。S5 先按「引擎已接入的族」判定，
    S7 接入 `game/families/registry.py` 后换成导入期自检结果，接口形状不变。
"""

from __future__ import annotations

import secrets

from pydantic import ValidationError

from common import miscCommon as misc
from common import mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from processor import familyService
from schemas.rule import RuleConfig

logger = get_logger("mahjong.rule")

# 已接入引擎的规则族：generic 为现有引擎，guangdong 复用同一引擎（03 §5）。
# sichuan（108 张/缺一门/多赢家）与 baishi（07 细则）尚未接入 → ready=false，开桌拦截。
ENGINE_READY_CODES = ("generic", "guangdong")

MAX_TEMPLATE_LIMIT = 100


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
    """族是否可开桌：引擎已接入 + 能力声明可解析。"""
    engineCode = _text(row, "engineCode")
    if engineCode not in ENGINE_READY_CODES:
        return False
    capability = row.get("capabilityJson")
    if not isinstance(capability, dict) or not capability:
        return False
    tileSet = str(capability.get("tile_set") or row.get("tileSetCode") or "")
    return tileSet in ("108", "136")


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
    "draw_penalty": "RULE_DRAW_PENALTY_INVALID",
    "rounds_per_game": "RULE_ROUNDS_INVALID",
    "claim_window_seconds": "RULE_CLAIM_WINDOW_INVALID",
}


def _raiseConfigError(error: ValidationError):
    """把 Pydantic 校验错误映射成 04 §10 的细粒度错误码。"""
    errors = error.errors()
    first = errors[0] if errors else {}
    loc = first.get("loc") or ()
    field = str(loc[0]) if loc else ""
    code = _FIELD_ERROR_CODE.get(field, "RULE_CONFIG_INVALID")
    message = str(first.get("msg") or "规则配置不合法").replace("Value error, ", "")
    raise _configError(code, message)


def _assertCapability(capability: dict, config: RuleConfig) -> None:
    """族能力白名单（03 §2.2）。S5 只覆盖会直接改变结算口径的项，其余随 S7 补齐。"""
    if capability.get("fan_cap_allowed") is False and config.fan_cap is not None:
        raise _configError("RULE_FAN_CAP_UNSUPPORTED", "当前规则族不支持封顶")
    if capability.get("allow_chow") is False and config.allow_chow:
        raise _configError("RULE_SWITCH_UNSUPPORTED", "当前规则族不支持「可以吃」")
    fanModes = capability.get("fan_modes")
    if isinstance(fanModes, list) and fanModes and config.fan_mode not in fanModes:
        raise _configError(
            "RULE_SWITCH_UNSUPPORTED", f"当前规则族不支持「{config.fan_mode}」计分方式"
        )


def loadRuleFamily(ruleFamilyCode: str) -> dict:
    """取族（ENABLED）；不存在 → 404 RULE_FAMILY_NOT_FOUND。"""
    code = (ruleFamilyCode or "").strip()
    row = mysqlCommon.query_mj_rule_family_by_code(code) if code else {}
    if not row:
        raise _configError("RULE_FAMILY_NOT_FOUND", "规则族不存在", 404)
    return row


def validateConfig(ruleFamilyCode: str, rawConfig: dict) -> RuleConfig:
    """族存在性 + 强校验 + 能力白名单，返回校验后的 RuleConfig。"""
    family = loadRuleFamily(ruleFamilyCode)
    try:
        config = RuleConfig.model_validate(rawConfig or {})
    except ValidationError as error:
        _raiseConfigError(error)
    capability = family.get("capabilityJson")
    _assertCapability(capability if isinstance(capability, dict) else {}, config)
    return config


def summaryText(config: RuleConfig) -> str:
    """一句话摘要（04 §5 validate 的 summary）。"""
    parts = [
        f"底分 {config.base_score}",
        "2 的 N 次方" if config.fan_mode == "exponential" else "线性累加",
    ]
    if config.fan_cap is not None:
        parts.append(f"封顶 {config.fan_cap} 番")
    parts.append("可以吃" if config.allow_chow else "不能吃")
    if config.turn_timeout.enabled:
        parts.append(f"限时 {config.turn_timeout.seconds} 秒")
    else:
        parts.append("不限时")
    if config.kong_score.enabled:
        parts.append(
            f"杠分 明{config.kong_score.exposed}/暗{config.kong_score.hidden}/补{config.kong_score.added}"
        )
    else:
        parts.append("杠不计分")
    parts.append("听牌提示开" if config.ting_hint.enabled else "无听牌提示")
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
    limit: int = MAX_TEMPLATE_LIMIT,
) -> list[dict]:
    """本家庭模板 + 全局预置（04 §5 #18）；只列启用项。"""
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
    config = source.get("configJson")
    now = misc.getTime()
    dataSet = {
        "templateCode": _newTemplateCode(_text(source, "ruleFamilyCode")),
        "familyID": familyID,
        "ruleFamilyCode": _text(source, "ruleFamilyCode"),
        "templateName": name,
        "description": _text(source, "description")[:400],
        "configJson": config if isinstance(config, dict) else {},
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


def openableTemplate(loginID: str, familyID: int, templateID: int) -> tuple[dict, RuleConfig]:
    """开桌用：模板必须是本家庭可见、启用、族已就绪（04 §6）。

    返回 (模板行, 强校验后的 RuleConfig)；失败抛 404/400，**不写任何表**。
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
    return row, config
