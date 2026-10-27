"""家庭域服务：家庭、成员、角色与家庭上下文（01 §6、02 §3.2–3.4、04 §3/§4）。

职责：
  1) `mj_family` / `mj_family_member` / `mj_user_pref` 的读写与权限校验；
  2) 成员变更与审计（`mj_audit_log`）在同一事务内完成（01 §7.4）；
  3) 对外提供「家庭上下文」判定：`assertMember` / `assertFamilyAdmin`，供 deps 与后续
     room/rule/skin 服务复用（S5/S8 直接调用，不再各自拼权限）。

红线：
  - 家庭域查询一律经 `mysqlCommon` 且 SQL 带 `familyID`，禁止内存过滤（01 §6.3-1）；
  - 跨家庭一律 403 且不泄露资源是否存在：统一文案「无权访问该家庭资源」（01 §6.3-2）；
  - 不建数据库外键，关系由本层事务保证；
  - 成员角色只有 OWNER / ADMIN / MEMBER，owner 全局唯一（`transferOwner` 内收敛）；
  - 审计 detail 不得含口令、验证码（04 §2.3）。
"""

from __future__ import annotations

import re
import secrets

from common import accountClient
from common import miscCommon as misc
from common import mysqlCommon as mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from processor import accountService

logger = get_logger("mahjong.family")

# ---------------------------------------------------------------- 枚举与常量

ROLE_OWNER = "OWNER"
ROLE_ADMIN = "ADMIN"
ROLE_MEMBER = "MEMBER"
MEMBER_ROLE_LIST = (ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER)
# 添加成员时允许直接指定的角色（OWNER 只能通过转让获得，04 §3）
ASSIGNABLE_ROLE_LIST = (ROLE_ADMIN, ROLE_MEMBER)

STATUS_ACTIVE = "ACTIVE"
STATUS_DISABLED = "DISABLED"
STATUS_LEFT = "LEFT"
MEMBER_STATUS_LIST = (STATUS_ACTIVE, STATUS_DISABLED, STATUS_LEFT)

FAMILY_ENABLED = "ENABLED"
FAMILY_DISABLED = "DISABLED"

# 04 §3：family_code ^[a-z][a-z0-9_]{1,31}$
FAMILY_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_FAMILY_NAME_MAX_LEN = 64

# 审计动作码（S4）
ACTION_FAMILY_CREATE = "FAMILY_CREATE"
ACTION_FAMILY_UPDATE = "FAMILY_UPDATE"
ACTION_MEMBER_ADD = "MEMBER_ADD"
ACTION_MEMBER_UPDATE = "MEMBER_UPDATE"
ACTION_MEMBER_REMOVE = "MEMBER_REMOVE"
ACTION_OWNER_TRANSFER = "OWNER_TRANSFER"

# 跨家庭统一文案：不区分「不存在」与「无权」，避免资源探测（01 §6.3-2）
_FORBIDDEN_MESSAGE = "无权访问该家庭资源"

# 偏好默认值（04 §4）
DEFAULT_SOUND_ENABLED = True
DEFAULT_SOUND_VOLUME = 70
DEFAULT_CHAT_SOUND = True
DEFAULT_SHOW_TENPAI = True


class FamilyServiceError(BizError):
    """家庭域业务异常（HTTP 状态 + 错误码 + 中文提示）。"""


# ---------------------------------------------------------------- 小工具


def _forbidden() -> FamilyServiceError:
    return FamilyServiceError("NOT_FAMILY_MEMBER", _FORBIDDEN_MESSAGE, 403)


def _adminRequired() -> FamilyServiceError:
    return FamilyServiceError("NOT_FAMILY_ADMIN", "需要家庭管理员权限", 403)


def _badRequest(code: str, message: str) -> FamilyServiceError:
    return FamilyServiceError(code, message, 400)


def _familyIDOf(row: dict) -> int:
    return int(row.get("recID") or 0)


def _flag(value) -> bool:
    """CHAR(1) 布尔列（'1'/'0'，历史数据可能是空串）。"""
    return str(value or "").strip() in ("1", "true", "True")


def _flagText(value: bool) -> str:
    return "1" if value else "0"


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def familyOut(row: dict, memberRole: str = "") -> dict:
    """04 §3 的 family 结构（member_role 为当前用户的角色）。"""
    return {
        "family_code": _text(row, "familyCode"),
        "family_name": _text(row, "familyName"),
        "owner_login_id": _text(row, "ownerLoginID"),
        "default_rule_family_code": _text(row, "defaultRuleFamilyCode") or None,
        "default_skin_code": _text(row, "defaultSkinCode") or None,
        "member_role": memberRole,
        "status": _text(row, "familyStatus") or FAMILY_ENABLED,
        "sort_order": int(row.get("sortOrder") or 0),
    }


def memberOut(row: dict) -> dict:
    """04 §3 的 member 结构。"""
    loginID = _text(row, "loginID")
    return {
        "login_id": loginID,
        "nick_name": _text(row, "nickName") or loginID,
        "member_role": _text(row, "memberRole"),
        "member_status": _text(row, "memberStatus"),
        "joined_ymdhms": _text(row, "joinedYMDHMS"),
    }


def _audit(
    familyID: int,
    operatorLoginID: str,
    actionCode: str,
    targetType: str,
    targetID: str,
    detail: dict | None,
    clientIP: str,
) -> None:
    """写审计：调用方必须已在事务内（与业务写入同生共死）。"""
    recID = mysqlCommon.write_mj_audit_log(
        familyID=familyID,
        operatorLoginID=operatorLoginID,
        actionCode=actionCode,
        targetType=targetType,
        targetID=targetID,
        detail=detail or {},
        clientIP=clientIP,
    )
    if recID <= 0:
        # 审计失败不能让业务静默通过：抛错触发整体回滚（01 §7.4）
        raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)


# ---------------------------------------------------------------- 家庭上下文


def _loadMemberRow(familyID: int, loginID: str) -> dict:
    return mysqlCommon.query_mj_family_member(familyID, loginID)


def assertMember(loginID: str, familyCode: str, requireEnabled: bool = False) -> dict:
    """家庭上下文解析：家庭存在 + 当前用户是 ACTIVE 成员。

    出参: {"familyID", "familyCode", "memberRole", "familyStatus", "family"}
    失败一律 403 NOT_FAMILY_MEMBER（不区分「家庭不存在」与「不是成员」）；
    家庭停用且 requireEnabled=True 时 403 FAMILY_DISABLED。
    """
    code = (familyCode or "").strip()
    if not code:
        raise _forbidden()

    family = mysqlCommon.query_mj_family_by_code(code)
    if not family:
        raise _forbidden()

    familyID = _familyIDOf(family)
    member = _loadMemberRow(familyID, loginID)
    if not member or _text(member, "memberStatus") != STATUS_ACTIVE:
        raise _forbidden()

    familyStatus = _text(family, "familyStatus") or FAMILY_ENABLED
    if requireEnabled and familyStatus != FAMILY_ENABLED:
        # 04 §3：停用家庭的成员仍可登录，但房间/模板/皮肤等资源接口一律拒绝
        raise FamilyServiceError("FAMILY_DISABLED", "该家庭已停用", 403)

    return {
        "familyID": familyID,
        "familyCode": _text(family, "familyCode"),
        "memberRole": _text(member, "memberRole"),
        "familyStatus": familyStatus,
        "family": family,
    }


def assertMemberOfFamilyID(
    loginID: str, familyID: int, requireEnabled: bool = False
) -> dict:
    """按 familyID 解析家庭上下文（S5：房间/模板/战绩等资源自带 familyID）。

    资源类接口先拿到资源行，再用资源的 familyID 校验成员关系——不信任请求参数里的
    family_code，避免「凭别人的 family_code 读到我家的房间」。
    """
    familyID = int(familyID or 0)
    if familyID <= 0:
        raise _forbidden()
    family = mysqlCommon.query_mj_family_by_id(familyID)
    if not family:
        # 家庭已物理删除：对非成员同样按无权处理，不泄露内部状态
        raise _forbidden()
    code = _text(family, "familyCode")
    return assertMember(loginID, code, requireEnabled=requireEnabled)


def assertFamilyAdmin(
    loginID: str, familyCode: str, operatorIsSystemAdmin: bool = False
) -> dict:
    """owner/admin 校验；返回结构同 assertMember。"""
    context = assertMember(loginID, familyCode)
    if operatorIsSystemAdmin:
        return context
    if context["memberRole"] not in (ROLE_OWNER, ROLE_ADMIN):
        raise _adminRequired()
    return context


def assertOwner(loginID: str, familyCode: str, operatorIsSystemAdmin: bool = False) -> dict:
    """仅 owner（或系统管理员）可执行：转让、family_status 变更。"""
    context = assertMember(loginID, familyCode)
    if operatorIsSystemAdmin:
        return context
    if context["memberRole"] != ROLE_OWNER:
        raise _adminRequired()
    return context


# ---------------------------------------------------------------- 我的家庭


def listMyFamilies(loginID: str) -> list[dict]:
    """我的家庭：join 成员表，只取 ACTIVE 成员关系（02 §8）。"""
    rows = mysqlCommon.query_mj_family_list_by_login(loginID)
    result = []
    for row in rows:
        result.append(familyOut(row, _text(row, "memberRole")))
    return result


def _prefRow(loginID: str) -> dict:
    return mysqlCommon.query_mj_user_pref_by_login(loginID)


def currentFamilyCode(loginID: str) -> str | None:
    """当前家庭：`mj_user_pref.lastFamilyID` 指向的家庭；失效时回落到第一个 ACTIVE 家庭。"""
    families = listMyFamilies(loginID)
    if not families:
        return None

    pref = _prefRow(loginID)
    lastFamilyID = int(pref.get("lastFamilyID") or 0) if pref else 0
    if lastFamilyID > 0:
        family = mysqlCommon.query_mj_family_by_id(lastFamilyID)
        if family:
            member = _loadMemberRow(lastFamilyID, loginID)
            if member and _text(member, "memberStatus") == STATUS_ACTIVE:
                return _text(family, "familyCode")

    return families[0]["family_code"]


def ensureDefaultFamily(loginID: str) -> str | None:
    """登录后补写 `lastFamilyID`（04 §2）：为空且仅有一个家庭时自动选中。

    出参：当前家庭编码（没有家庭时为 None）。
    """
    families = listMyFamilies(loginID)
    if not families:
        return None

    pref = _prefRow(loginID)
    lastFamilyID = int(pref.get("lastFamilyID") or 0) if pref else 0
    if lastFamilyID > 0 and mysqlCommon.query_mj_family_by_id(lastFamilyID):
        return currentFamilyCode(loginID)

    if len(families) == 1:
        family = mysqlCommon.query_mj_family_by_code(families[0]["family_code"])
        familyID = _familyIDOf(family)
        if familyID > 0:
            _saveLastFamily(loginID, familyID, families[0]["family_code"])
            return families[0]["family_code"]

    return currentFamilyCode(loginID)


# ---------------------------------------------------------------- 家庭 CRUD


def getFamily(loginID: str, familyCode: str) -> dict:
    """家庭详情：成员可读（停用家庭的成员仍可查看家庭本身）。"""
    context = assertMember(loginID, familyCode)
    return familyOut(context["family"], context["memberRole"])


def _generateFamilyCode(familyName: str) -> str:
    """按家庭名称生成候选编码：可 ASCII 化时用名称，否则用 fam 前缀 + 随机后缀。"""
    base = re.sub(r"[^a-z0-9]+", "_", (familyName or "").lower()).strip("_")[:24]
    if not base or not base[0].isalpha():
        base = "fam"
    return f"{base}_{secrets.token_hex(2)}"


def _validateFamilyName(familyName: str) -> str:
    name = (familyName or "").strip()
    if not name:
        raise _badRequest("FAMILY_NAME_REQUIRED", "请填写家庭名称")
    if len(name) > _FAMILY_NAME_MAX_LEN:
        raise _badRequest("FAMILY_NAME_TOO_LONG", "家庭名称最多 64 字")
    return name


def _validateFamilyCode(familyCode: str) -> str:
    code = (familyCode or "").strip()
    if not FAMILY_CODE_PATTERN.match(code):
        raise _badRequest(
            "FAMILY_CODE_INVALID", "家庭编码需以小写字母开头，只含小写字母、数字与下划线"
        )
    return code


def _nextFamilyCode(familyName: str, requestedCode: str) -> str:
    """显式编码：非法 400、已存在 409；未传编码：生成后重试。"""
    if requestedCode:
        code = _validateFamilyCode(requestedCode)
        if mysqlCommon.query_mj_family_by_code(code):
            raise FamilyServiceError("FAMILY_CODE_EXISTS", "家庭编码已被占用", 409)
        return code

    for _ in range(5):
        candidate = _generateFamilyCode(familyName)
        if not mysqlCommon.query_mj_family_by_code(candidate):
            return candidate
    raise FamilyServiceError("FAMILY_CODE_EXHAUSTED", "家庭编码生成失败，请重试", 500)


def _saveLastFamily(loginID: str, familyID: int, operatorLoginID: str = "") -> None:
    """写 `mj_user_pref.lastFamilyID`（无记录则先建一条默认偏好）。"""
    pref = _prefRow(loginID)
    now = misc.getTime()
    if pref:
        mysqlCommon.update_mj_user_pref_by_login(
            loginID,
            {
                "lastFamilyID": familyID,
                "modifyID": operatorLoginID or loginID,
                "modifyYMDHMS": now,
            },
        )
        return

    recID = mysqlCommon.insert_mj_user_pref(
        mysqlCommon.MJ_USER_PREF_TABLE,
        {
            "loginID": loginID,
            "lastFamilyID": familyID,
            "skinCode": "",
            "soundEnabledFlag": _flagText(DEFAULT_SOUND_ENABLED),
            "soundVolume": DEFAULT_SOUND_VOLUME,
            "chatSoundFlag": _flagText(DEFAULT_CHAT_SOUND),
            "showTenpaiFlag": _flagText(DEFAULT_SHOW_TENPAI),
            "regID": operatorLoginID or loginID,
            "regYMDHMS": now,
            "delFlag": "0",
        },
    )
    if recID <= 0:
        raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)


def createFamily(
    loginID: str,
    familyName: str,
    familyCode: str = "",
    clientIP: str = "",
    defaultRuleFamilyCode: str = "",
    defaultSkinCode: str = "",
) -> dict:
    """创建家庭：一个事务内写 family + 成员 OWNER + pref.lastFamilyID + 审计。

    同一 family_code 重复创建一律 409 `FAMILY_CODE_EXISTS`（在接口层固定这一选择）。
    """
    name = _validateFamilyName(familyName)
    code = _nextFamilyCode(name, familyCode)
    now = misc.getTime()

    with mysqlCommon.transaction():
        familyID = mysqlCommon.insert_mj_family(
            mysqlCommon.MJ_FAMILY_TABLE,
            {
                "familyCode": code,
                "familyName": name,
                "ownerLoginID": loginID,
                "defaultRuleFamilyCode": defaultRuleFamilyCode or "",
                "defaultSkinCode": defaultSkinCode or "",
                "familyStatus": FAMILY_ENABLED,
                "sortOrder": 0,
                "regID": loginID,
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
        if familyID <= 0:
            # 并发下唯一索引可能先被占用：回查后给出 409 而不是 500
            if mysqlCommon.query_mj_family_by_code(code):
                raise FamilyServiceError("FAMILY_CODE_EXISTS", "家庭编码已被占用", 409)
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

        memberRecID = mysqlCommon.insert_mj_family_member(
            mysqlCommon.MJ_FAMILY_MEMBER_TABLE,
            {
                "familyMemberKey": f"{familyID}_{loginID}",
                "familyID": familyID,
                "loginID": loginID,
                "memberRole": ROLE_OWNER,
                "memberStatus": STATUS_ACTIVE,
                "joinedYMDHMS": now,
                "regID": loginID,
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
        if memberRecID <= 0:
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

        _saveLastFamily(loginID, familyID, loginID)
        _audit(
            familyID,
            loginID,
            ACTION_FAMILY_CREATE,
            "FAMILY",
            code,
            {"family_name": name, "family_code": code},
            clientIP,
        )

    return getFamily(loginID, code)


def updateFamily(
    loginID: str,
    familyCode: str,
    familyName: str | None = None,
    defaultRuleFamilyCode: str | None = None,
    defaultSkinCode: str | None = None,
    familyStatus: str | None = None,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """更新家庭：owner/admin；`familyStatus` 仅系统管理员可改（04 §3 之外的运维口子）。"""
    if familyStatus is not None:
        # 停用/启用是运维动作，不能交给家庭内部管理员自行决定（避免成员被内部锁死）
        if not operatorIsSystemAdmin:
            raise FamilyServiceError(
                "NOT_FAMILY_ADMIN", "只有系统管理员可以停用或启用家庭", 403
            )
        context = assertMember(loginID, familyCode)
    else:
        context = assertFamilyAdmin(loginID, familyCode, operatorIsSystemAdmin)

    familyID = context["familyID"]
    before = familyOut(context["family"], context["memberRole"])
    dataSet: dict = {}
    detail: dict = {}

    if familyName is not None:
        dataSet["familyName"] = _validateFamilyName(familyName)

    if defaultRuleFamilyCode is not None:
        ruleFamilyCode = (defaultRuleFamilyCode or "").strip()
        if ruleFamilyCode:
            if not mysqlCommon.query_mj_rule_family_by_code(ruleFamilyCode):
                raise _badRequest("RULE_FAMILY_NOT_FOUND", "规则族不存在")
            dataSet["defaultRuleFamilyCode"] = ruleFamilyCode
        else:
            dataSet["defaultRuleFamilyCode"] = None

    if defaultSkinCode is not None:
        skinCode = (defaultSkinCode or "").strip()
        if skinCode:
            _assertSkinVisible(skinCode, familyID)
            dataSet["defaultSkinCode"] = skinCode
        else:
            dataSet["defaultSkinCode"] = None

    if familyStatus is not None:
        status = (familyStatus or "").strip().upper()
        if status not in (FAMILY_ENABLED, FAMILY_DISABLED):
            raise _badRequest("FAMILY_STATUS_INVALID", "家庭状态只支持 ENABLED / DISABLED")
        dataSet["familyStatus"] = status

    if not dataSet:
        return before

    dataSet["modifyID"] = loginID
    dataSet["modifyYMDHMS"] = misc.getTime()

    with mysqlCommon.transaction():
        affected = mysqlCommon.update_mj_family_by_id(familyID, dataSet)
        if affected < 0:
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        after = familyOut(mysqlCommon.query_mj_family_by_id(familyID), context["memberRole"])
        for key, value in after.items():
            if key in ("family_code", "member_role"):
                continue
            if before.get(key) != value:
                detail[key] = {"before": before.get(key), "after": value}
        _audit(
            familyID,
            loginID,
            ACTION_FAMILY_UPDATE,
            "FAMILY",
            context["familyCode"],
            detail,
            clientIP,
        )

    return getFamily(loginID, context["familyCode"])


# ---------------------------------------------------------------- 成员


def listMembers(loginID: str, familyCode: str, includeLeft: bool = False) -> list[dict]:
    """成员列表：家庭成员可读（仅本家庭，SQL 带 familyID）。"""
    context = assertMember(loginID, familyCode)
    rows = mysqlCommon.query_mj_family_member_list(context["familyID"], includeLeft=includeLeft)
    return [memberOut(row) for row in rows]


def initializeUserProfile(targetLoginID: str, operatorLoginID: str) -> str:
    """确保目标账号有 USER_BASIC 档案（04 §3：添加成员时同步）。

    说明：acis 的 A3A0 依赖**目标用户会话**，无法由他人代取，因此这里只能补一条最小档案；
    昵称等资料在该用户下次登录时由 accountService.syncUserBasic 补齐。
    """
    return accountService.ensureUserBasic(targetLoginID, operatorLoginID)


def addMember(
    loginID: str,
    familyCode: str,
    memberLoginID: str,
    memberRole: str = ROLE_MEMBER,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """添加成员：owner/admin；账号须存在于账号服务（AIA0）。

    - 账号不存在 → 404 `ACCOUNT_USER_NOT_FOUND`；账号服务不可达 → 503；
    - 已是家庭成员（ACTIVE/DISABLED）→ 400 `MEMBER_ALREADY_EXISTS`；
    - 已退出（LEFT）→ 复用原行复活为 ACTIVE（保证 familyMemberKey 唯一）。
    """
    context = assertFamilyAdmin(loginID, familyCode, operatorIsSystemAdmin)
    familyID = context["familyID"]

    target = accountService.normalizeLoginID(memberLoginID)
    if not target:
        raise _badRequest("ACCOUNT_LOGIN_ID_INVALID", "请填写要添加的账号")

    role = (memberRole or ROLE_MEMBER).strip().upper()
    if role not in ASSIGNABLE_ROLE_LIST:
        raise _badRequest("MEMBER_ROLE_INVALID", "添加成员只能指定 ADMIN 或 MEMBER")

    existing = _loadMemberRow(familyID, target)
    existingStatus = _text(existing, "memberStatus") if existing else ""
    if existing and existingStatus in (STATUS_ACTIVE, STATUS_DISABLED):
        raise _badRequest("MEMBER_ALREADY_EXISTS", "该账号已是家庭成员")

    exists, errCode = accountClient.chkUserExistEx(target)
    if errCode == accountClient.ERR_SVC_OFFLINE:
        raise FamilyServiceError(
            "ACCOUNT_SERVICE_UNAVAILABLE", "账号服务暂时不可用，请稍后再试", 503
        )
    if not exists:
        raise FamilyServiceError("ACCOUNT_USER_NOT_FOUND", "账号不存在", 404)

    initializeUserProfile(target, loginID)

    now = misc.getTime()
    with mysqlCommon.transaction():
        if existing:
            # 复活：复用原行，避免 familyMemberKey 唯一键挡住重新加入
            affected = mysqlCommon.update_mj_family_member_by_id(
                familyID,
                int(existing.get("recID") or 0),
                {
                    "memberRole": role,
                    "memberStatus": STATUS_ACTIVE,
                    "joinedYMDHMS": now,
                    "modifyID": loginID,
                    "modifyYMDHMS": now,
                    "delFlag": "0",
                },
            )
            if affected < 0:
                raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
        else:
            recID = mysqlCommon.insert_mj_family_member(
                mysqlCommon.MJ_FAMILY_MEMBER_TABLE,
                {
                    "familyMemberKey": f"{familyID}_{target}",
                    "familyID": familyID,
                    "loginID": target,
                    "memberRole": role,
                    "memberStatus": STATUS_ACTIVE,
                    "joinedYMDHMS": now,
                    "regID": loginID,
                    "regYMDHMS": now,
                    "delFlag": "0",
                },
            )
            if recID <= 0:
                raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

        _audit(
            familyID,
            loginID,
            ACTION_MEMBER_ADD,
            "MEMBER",
            target,
            {"member_role": role, "revived": bool(existing)},
            clientIP,
        )

    return memberOut(_loadMemberRow(familyID, target))


def updateMember(
    loginID: str,
    familyCode: str,
    targetLoginID: str,
    memberRole: str | None = None,
    memberStatus: str | None = None,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """更新成员：owner/admin。

    - `member_role=OWNER` 走转让流程（仅当前 owner 或系统管理员）；
    - 直接改 owner 的角色 → 400 `OWNER_MUST_TRANSFER`（必须先转让）；
    - `member_status=LEFT` 等价移出成员（保留行，便于重新加入）；
    - 停用 owner → 400 `MEMBER_OWNER_PROTECTED`。
    """
    target = accountService.normalizeLoginID(targetLoginID)
    if not target:
        raise _badRequest("ACCOUNT_LOGIN_ID_INVALID", "缺少成员账号")

    if memberRole is not None:
        role = (memberRole or "").strip().upper()
        if role not in MEMBER_ROLE_LIST:
            raise _badRequest("MEMBER_ROLE_INVALID", "成员角色只支持 OWNER / ADMIN / MEMBER")
        if role == ROLE_OWNER:
            return transferOwner(
                loginID,
                familyCode,
                target,
                clientIP=clientIP,
                operatorIsSystemAdmin=operatorIsSystemAdmin,
            )
    else:
        role = None

    status = None
    if memberStatus is not None:
        status = (memberStatus or "").strip().upper()
        if status not in MEMBER_STATUS_LIST:
            raise _badRequest(
                "MEMBER_STATUS_INVALID", "成员状态只支持 ACTIVE / DISABLED / LEFT"
            )
        if status == STATUS_LEFT:
            return removeMember(
                loginID,
                familyCode,
                target,
                clientIP=clientIP,
                operatorIsSystemAdmin=operatorIsSystemAdmin,
            )

    context = assertFamilyAdmin(loginID, familyCode, operatorIsSystemAdmin)
    familyID = context["familyID"]

    member = _loadMemberRow(familyID, target)
    if not member:
        raise FamilyServiceError("MEMBER_NOT_FOUND", "成员不存在", 404)

    currentRole = _text(member, "memberRole")
    if currentRole == ROLE_OWNER:
        # owner 不能被降级/停用：只能先转让（04 §3）
        if target == loginID:
            raise _badRequest("OWNER_MUST_TRANSFER", "请先把家庭管理员转让给其他成员")
        raise FamilyServiceError("NOT_FAMILY_ADMIN", "不能修改家庭管理员的角色", 403)

    before = memberOut(member)
    dataSet: dict = {}
    if role and role != currentRole:
        dataSet["memberRole"] = role
    if status and status != before["member_status"]:
        dataSet["memberStatus"] = status

    if not dataSet:
        return before

    now = misc.getTime()
    dataSet["modifyID"] = loginID
    dataSet["modifyYMDHMS"] = now

    with mysqlCommon.transaction():
        affected = mysqlCommon.update_mj_family_member_by_id(
            familyID, int(member.get("recID") or 0), dataSet
        )
        if affected < 0:
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

        after = memberOut(_loadMemberRow(familyID, target))
        _audit(
            familyID,
            loginID,
            ACTION_MEMBER_UPDATE,
            "MEMBER",
            target,
            {
                "before": {"member_role": before["member_role"], "member_status": before["member_status"]},
                "after": {"member_role": after["member_role"], "member_status": after["member_status"]},
            },
            clientIP,
        )

    return after


def removeMember(
    loginID: str,
    familyCode: str,
    targetLoginID: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """移出成员：owner/admin 可移除他人；成员可自行退出；owner 不可被移除/自移除。

    实现为 `memberStatus='LEFT'`（保留行，避免 familyMemberKey 唯一键导致无法重新加入）。
    """
    context = assertMember(loginID, familyCode)
    familyID = context["familyID"]
    target = accountService.normalizeLoginID(targetLoginID)
    if not target:
        raise _badRequest("ACCOUNT_LOGIN_ID_INVALID", "缺少成员账号")

    isSelf = target == loginID
    isAdmin = operatorIsSystemAdmin or context["memberRole"] in (ROLE_OWNER, ROLE_ADMIN)
    if not isAdmin and not isSelf:
        raise _adminRequired()

    member = _loadMemberRow(familyID, target)
    if not member or _text(member, "memberStatus") == STATUS_LEFT:
        raise FamilyServiceError("MEMBER_NOT_FOUND", "成员不存在", 404)

    memberRole = _text(member, "memberRole")
    if memberRole == ROLE_OWNER:
        raise _badRequest("MEMBER_OWNER_PROTECTED", "不能移除家庭管理员，请先转让")

    now = misc.getTime()
    with mysqlCommon.transaction():
        affected = mysqlCommon.update_mj_family_member_by_id(
            familyID,
            int(member.get("recID") or 0),
            {
                "memberStatus": STATUS_LEFT,
                "modifyID": loginID,
                "modifyYMDHMS": now,
            },
        )
        if affected < 0:
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

        # 被移除者的当前家庭若指向本家庭，清空，避免下一次进站落到无权家庭
        pref = _prefRow(target)
        if pref and int(pref.get("lastFamilyID") or 0) == familyID:
            mysqlCommon.update_mj_user_pref_by_login(
                target, {"lastFamilyID": None, "modifyID": loginID, "modifyYMDHMS": now}
            )

        _audit(
            familyID,
            loginID,
            ACTION_MEMBER_REMOVE,
            "MEMBER",
            target,
            {"member_role": memberRole, "self": isSelf},
            clientIP,
        )

    return {"ok": True}


def transferOwner(
    loginID: str,
    familyCode: str,
    targetLoginID: str,
    clientIP: str = "",
    operatorIsSystemAdmin: bool = False,
) -> dict:
    """转让家庭管理员：同一事务内完成「family.ownerLoginID + 新旧角色」，保证 owner 唯一。"""
    context = assertOwner(loginID, familyCode, operatorIsSystemAdmin)
    familyID = context["familyID"]

    target = accountService.normalizeLoginID(targetLoginID)
    if not target:
        raise _badRequest("ACCOUNT_LOGIN_ID_INVALID", "缺少成员账号")
    if target == context["family"]["ownerLoginID"]:
        # 幂等：已经是 owner 时不写库、不写审计
        return memberOut(_loadMemberRow(familyID, target))

    member = _loadMemberRow(familyID, target)
    if not member:
        raise FamilyServiceError("MEMBER_NOT_FOUND", "成员不存在", 404)
    if _text(member, "memberStatus") != STATUS_ACTIVE:
        raise _badRequest("MEMBER_NOT_ACTIVE", "只能把家庭管理员转让给正常状态的成员")

    oldOwner = context["family"]["ownerLoginID"]
    now = misc.getTime()

    with mysqlCommon.transaction():
        # 1) 目标升为 OWNER
        affected = mysqlCommon.update_mj_family_member_by_id(
            familyID,
            int(member.get("recID") or 0),
            {
                "memberRole": ROLE_OWNER,
                "memberStatus": STATUS_ACTIVE,
                "modifyID": loginID,
                "modifyYMDHMS": now,
            },
        )
        if affected < 0:
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

        # 2) 其余 OWNER（含原 owner）降为 ADMIN —— owner 唯一
        mysqlCommon.update_mj_family_member_clear_owner(familyID, target, loginID)
        if oldOwner and oldOwner != target:
            oldMember = _loadMemberRow(familyID, oldOwner)
            if oldMember and _text(oldMember, "memberRole") == ROLE_OWNER:
                mysqlCommon.update_mj_family_member_by_id(
                    familyID,
                    int(oldMember.get("recID") or 0),
                    {"memberRole": ROLE_ADMIN, "modifyID": loginID, "modifyYMDHMS": now},
                )

        # 3) 家庭主档的 ownerLoginID 同步
        affected = mysqlCommon.update_mj_family_by_id(
            familyID, {"ownerLoginID": target, "modifyID": loginID, "modifyYMDHMS": now}
        )
        if affected < 0:
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

        _audit(
            familyID,
            loginID,
            ACTION_OWNER_TRANSFER,
            "MEMBER",
            target,
            {"from": oldOwner, "to": target},
            clientIP,
        )

    return memberOut(_loadMemberRow(familyID, target))


# ---------------------------------------------------------------- 用户偏好


def _assertSkinVisible(skinCode: str, familyID: int) -> None:
    """皮肤可见性：全局内置（familyID=0）或本家庭自定义，且为 ENABLED（04 §4）。"""
    skin = mysqlCommon.query_mj_tile_skin_by_code(skinCode)
    if not skin:
        raise _badRequest("SKIN_NOT_VISIBLE", "皮肤不可用")
    skinFamilyID = int(skin.get("familyID") or 0)
    if skinFamilyID not in (0, int(familyID or 0)):
        raise _badRequest("SKIN_NOT_VISIBLE", "皮肤不可用")
    if _text(skin, "skinStatus") != FAMILY_ENABLED:
        raise _badRequest("SKIN_NOT_VISIBLE", "皮肤不可用")


def _prefOut(row: dict, lastFamilyCode: str | None, skinCode: str | None) -> dict:
    if not row:
        return {
            "last_family_code": lastFamilyCode,
            "skin_code": skinCode,
            "sound_enabled": DEFAULT_SOUND_ENABLED,
            "sound_volume": DEFAULT_SOUND_VOLUME,
            "chat_sound": DEFAULT_CHAT_SOUND,
            "show_tenpai": DEFAULT_SHOW_TENPAI,
        }

    volumeText = _text(row, "soundVolume")
    volume = int(volumeText) if volumeText.isdigit() else DEFAULT_SOUND_VOLUME
    return {
        "last_family_code": lastFamilyCode,
        "skin_code": skinCode,
        "sound_enabled": _flag(row.get("soundEnabledFlag")),
        "sound_volume": min(100, max(0, volume)),
        "chat_sound": _flag(row.get("chatSoundFlag")),
        "show_tenpai": _flag(row.get("showTenpaiFlag")),
    }


def getPref(loginID: str) -> dict:
    """04 §4 的偏好输出；`last_family_code` 与 `skin_code` 都按当前可见性收敛。"""
    row = _prefRow(loginID)
    lastFamilyCode = currentFamilyCode(loginID)

    skinCode = _text(row, "skinCode") if row else ""
    familyID = 0
    if lastFamilyCode:
        family = mysqlCommon.query_mj_family_by_code(lastFamilyCode)
        familyID = _familyIDOf(family)
    visibleSkin = ""
    if skinCode:
        skin = mysqlCommon.query_mj_tile_skin_by_code(skinCode)
        if skin and int(skin.get("familyID") or 0) in (0, familyID) and _text(skin, "skinStatus") == FAMILY_ENABLED:
            visibleSkin = skinCode

    return _prefOut(row, lastFamilyCode, visibleSkin or None)


def updatePref(loginID: str, patch: dict, clientIP: str = "") -> dict:
    """PUT /api/user/pref：局部更新，未传字段保持原值（04 §4）。"""
    row = _prefRow(loginID)
    dataSet: dict = {}

    if patch.get("last_family_code") is not None:
        code = str(patch.get("last_family_code")).strip()
        if code:
            context = assertMember(loginID, code)  # 非成员 → 403 NOT_FAMILY_MEMBER
            dataSet["lastFamilyID"] = context["familyID"]
        else:
            dataSet["lastFamilyID"] = None

    if patch.get("skin_code") is not None:
        skinCode = str(patch.get("skin_code")).strip()
        if skinCode:
            currentCode = currentFamilyCode(loginID)
            familyID = 0
            if currentCode:
                familyID = _familyIDOf(mysqlCommon.query_mj_family_by_code(currentCode))
            _assertSkinVisible(skinCode, familyID)
            dataSet["skinCode"] = skinCode
        else:
            dataSet["skinCode"] = None  # 空串 = 回到默认皮肤

    if "sound_volume" in patch:
        volume = patch.get("sound_volume")
        try:
            volume = int(volume)
        except (TypeError, ValueError):
            raise _badRequest("SOUND_VOLUME_INVALID", "音效音量必须是 0-100 的整数")
        if volume < 0 or volume > 100:
            raise _badRequest("SOUND_VOLUME_INVALID", "音效音量必须是 0-100 的整数")
        dataSet["soundVolume"] = volume

    for field, column in (
        ("sound_enabled", "soundEnabledFlag"),
        ("chat_sound", "chatSoundFlag"),
        ("show_tenpai", "showTenpaiFlag"),
    ):
        if field in patch and patch[field] is not None:
            dataSet[column] = _flagText(bool(patch[field]))

    now = misc.getTime()
    if row:
        if dataSet:
            dataSet["modifyID"] = loginID
            dataSet["modifyYMDHMS"] = now
            affected = mysqlCommon.update_mj_user_pref_by_login(loginID, dataSet)
            if affected < 0:
                raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
    else:
        recID = mysqlCommon.insert_mj_user_pref(
            mysqlCommon.MJ_USER_PREF_TABLE,
            {
                "loginID": loginID,
                "lastFamilyID": dataSet.pop("lastFamilyID", None),
                "skinCode": dataSet.pop("skinCode", "") or "",
                "soundEnabledFlag": dataSet.pop("soundEnabledFlag", _flagText(DEFAULT_SOUND_ENABLED)),
                "soundVolume": dataSet.pop("soundVolume", DEFAULT_SOUND_VOLUME),
                "chatSoundFlag": dataSet.pop("chatSoundFlag", _flagText(DEFAULT_CHAT_SOUND)),
                "showTenpaiFlag": dataSet.pop("showTenpaiFlag", _flagText(DEFAULT_SHOW_TENPAI)),
                "regID": loginID,
                "regYMDHMS": now,
                "delFlag": "0",
            },
        )
        if recID <= 0:
            raise FamilyServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

    return getPref(loginID)


# ---------------------------------------------------------------- 初始化脚本


def bootstrapFamily(
    ownerLoginID: str,
    familyName: str,
    familyCode: str,
    defaultRuleFamilyCode: str = "generic",
    defaultSkinCode: str = "css-classic",
    clientIP: str = "bootstrap",
) -> dict:
    """tools/bootstrapFamily.py 的唯一实现：幂等确保家庭 / OWNER 成员 / lastFamilyID。"""
    name = _validateFamilyName(familyName)
    code = _validateFamilyCode(familyCode)

    result = {"familyID": 0, "familyCreated": False, "memberCreated": False, "prefUpdated": False}
    now = misc.getTime()

    with mysqlCommon.transaction():
        family = mysqlCommon.query_mj_family_by_code(code)
        if family:
            familyID = _familyIDOf(family)
        else:
            familyID = mysqlCommon.insert_mj_family(
                mysqlCommon.MJ_FAMILY_TABLE,
                {
                    "familyCode": code,
                    "familyName": name,
                    "ownerLoginID": ownerLoginID,
                    "defaultRuleFamilyCode": defaultRuleFamilyCode or "",
                    "defaultSkinCode": defaultSkinCode or "",
                    "familyStatus": FAMILY_ENABLED,
                    "sortOrder": 0,
                    "regID": ownerLoginID,
                    "regYMDHMS": now,
                    "delFlag": "0",
                },
            )
            if familyID <= 0:
                raise FamilyServiceError("DB_WRITE_FAILED", "家庭写入失败", 500)
            result["familyCreated"] = True
            _audit(
                familyID,
                ownerLoginID,
                ACTION_FAMILY_CREATE,
                "FAMILY",
                code,
                {"family_name": name, "scene": "bootstrap"},
                clientIP,
            )
        result["familyID"] = familyID

        member = _loadMemberRow(familyID, ownerLoginID)
        if member:
            if (
                _text(member, "memberRole") != ROLE_OWNER
                or _text(member, "memberStatus") != STATUS_ACTIVE
            ):
                mysqlCommon.update_mj_family_member_by_id(
                    familyID,
                    int(member.get("recID") or 0),
                    {
                        "memberRole": ROLE_OWNER,
                        "memberStatus": STATUS_ACTIVE,
                        "modifyID": ownerLoginID,
                        "modifyYMDHMS": now,
                    },
                )
            mysqlCommon.update_mj_family_member_clear_owner(familyID, ownerLoginID, ownerLoginID)
        else:
            recID = mysqlCommon.insert_mj_family_member(
                mysqlCommon.MJ_FAMILY_MEMBER_TABLE,
                {
                    "familyMemberKey": f"{familyID}_{ownerLoginID}",
                    "familyID": familyID,
                    "loginID": ownerLoginID,
                    "memberRole": ROLE_OWNER,
                    "memberStatus": STATUS_ACTIVE,
                    "joinedYMDHMS": now,
                    "regID": ownerLoginID,
                    "regYMDHMS": now,
                    "delFlag": "0",
                },
            )
            if recID <= 0:
                raise FamilyServiceError("DB_WRITE_FAILED", "成员写入失败", 500)
            result["memberCreated"] = True
            _audit(
                familyID,
                ownerLoginID,
                ACTION_MEMBER_ADD,
                "MEMBER",
                ownerLoginID,
                {"member_role": ROLE_OWNER, "scene": "bootstrap"},
                clientIP,
            )

        # 家庭主档的 owner 与成员关系保持一致
        if _text(family, "ownerLoginID") != ownerLoginID:
            mysqlCommon.update_mj_family_by_id(
                familyID,
                {"ownerLoginID": ownerLoginID, "modifyID": ownerLoginID, "modifyYMDHMS": now},
            )

        pref = _prefRow(ownerLoginID)
        if not pref or int(pref.get("lastFamilyID") or 0) != familyID:
            _saveLastFamily(ownerLoginID, familyID, ownerLoginID)
            result["prefUpdated"] = True

    return result
