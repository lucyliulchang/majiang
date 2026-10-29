"""账号域服务：登录 / 注册 / 找回口令 / 改密 / 登出 / 档案镜像。

职责（01 §5.1）：
  1) 把本系统账号动作翻译成 contentHub 账号服务（acis）的 CMD，并把 acis 错误码
     映射成本系统错误码（04 §2.5、§10）；
  2) 登录/注册/找回成功后同步 `USER_BASIC` 档案镜像（44 列不改，见 02 §3.1）；
  3) 角色映射：acis `roleName` 在 USER_ADMIN_ROLE_LIST（administrator/manager）内 → admin，
     否则 member；缺省 ACCOUNT_DEFAULT_ROLE；回写 acis 用 ROLE_ACCOUNT_ROLE。

红线（S3 硬约束）：
  - **本地绝不校验口令**：明文只在内存里参与 md5(passwd + loginID)，不落日志、不回显、不进 JWT；
  - 验证码只在 acis 侧生成与校验：本地只保存「发送时间 + 失败次数」，不存明文、不落库、不落 Redis；
  - 账号服务异常不得产生半登录状态：取不到资料即判 503，不写 USER_BASIC、不签 token；
  - 不新增账号表；USER_BASIC 结构不动。
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from typing import Any

from common import accountClient
from common import miscCommon as misc
from common import mysqlCommon as mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from config.basicSettings import (
    AUTH_VERIFY_CODE_EXPIRE_SECONDS,
    ROLE_ACCOUNT_ROLE,
    USER_ADMIN_ROLE_LIST,
)
from config.localSettings import settings

logger = get_logger("mahjong.account")

#本系统角色（01 §5.5）
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

#acis 错误码（04 §2.5）
ERR_OK = "B0"
ERR_SVC_OFFLINE = "CI"
ERR_CODE_MAP = {
    "B0": "OK",
    "B1": "ACCOUNT_AUTH_FAILED",       # 账号不存在（登录） / 发码步骤对外隐藏
    "B3": "ACCOUNT_AUTH_FAILED",       # 口令错
    "B4": "ACCOUNT_LOGIN_ID_EXISTS",   # 注册重复
    "B5": "ACCOUNT_AUTH_FAILED",       # 口令错
    "B6": "PASSWORD_REUSED",           # 新口令与旧口令相同
    "B7": "ACCOUNT_LOGIN_ID_INVALID",  # 登录号无效
    "B8": "UNAUTHORIZED",              # 会话失效
    "BA": "BAD_REQUEST",
    "BE": "ACCOUNT_REGISTER_DISABLED",
    "BM": "VERIFY_CODE_INVALID",
    "BN": "VERIFY_CODE_SEND_FAILED",
    "BS": "ACCOUNT_REGISTER_DISABLED",
    "BW": "ACCOUNT_LOGIN_ID_INVALID",
    "CS": "VERIFY_CODE_SEND_TOO_FAST",
    "CI": "ACCOUNT_SERVICE_UNAVAILABLE",
}

# 04 §2.1 / §2.2 校验口径
_LOGIN_ID_PATTERN = re.compile(r"^1[3-9]\d{9}$")
_VERIFY_CODE_PATTERN = re.compile(r"^\d{6}$")
_PASSWD_MIN_LEN = 6
_PASSWD_MAX_LEN = 32

#验证码场景（本地只用于分桶限流与前端文案）
SCENE_REGISTER = "register"
SCENE_RESET = "reset_password"
SCENE_LIST = (SCENE_REGISTER, SCENE_RESET)
#acis 侧验证码 TTL（仅用于对外 expire_seconds 文案）
VERIFY_CODE_EXPIRE_SECONDS = AUTH_VERIFY_CODE_EXPIRE_SECONDS

#USER_BASIC 中由 acis 档案映射的列（`USER_BASIC` 44 列的一部分，其余列不由本模块写）
_PROFILE_COLUMNS = (
    "openID",
    "roleName",
    "nickName",
    "realName",
    "gender",
    "avatarID",
    "mobilePhoneNo",
    "province",
    "city",
    "area",
    "address",
    "email",
    "PID",
    "photoIDFront",
    "photoIDBack",
    "photoID",
    "activeFlag",
)


class AccountServiceError(BizError):
    """业务异常（common.bizCommon.BizError 家族）：统一转成 {"detail": message, "code": code}。"""


# ---------------------------------------------------------------- 基础工具


def normalizeLoginID(loginID: str) -> str:
    """登录号归一：去空白，不做大小写变换（账号服务以手机号作登录号）。"""
    return (loginID or "").strip()


def hashPasswd(passwd: str, loginID: str) -> str:
    """口令哈希口径（04 §2.4）：md5(passwd + loginID)，只在后端计算，前端不哈希。

    仅用于转发 acis 与 USER_BASIC 镜像；本函数结果与明文都不进日志。
    """
    raw = f"{passwd or ''}{loginID or ''}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _validLoginID(loginID: str) -> bool:
    return bool(_LOGIN_ID_PATTERN.match(loginID or ""))


def _validatePasswd(passwd: str) -> None:
    text = passwd or ""
    if len(text) < _PASSWD_MIN_LEN:
        raise AccountServiceError("PASSWORD_TOO_SHORT", "密码长度不能少于 6 位", 400)
    if len(text) > _PASSWD_MAX_LEN:
        raise AccountServiceError("PASSWORD_TOO_SHORT", "密码长度不能超过 32 位", 400)
    if any(char.isspace() for char in text):
        raise AccountServiceError("BAD_REQUEST", "密码不能包含空格", 400)


def _validateVerifyCode(verifyCode: str) -> None:
    if not _VERIFY_CODE_PATTERN.match((verifyCode or "").strip()):
        raise AccountServiceError("VERIFY_CODE_REQUIRED", "请先获取验证码", 400)


def _svcUnavailable() -> AccountServiceError:
    return AccountServiceError(
        "ACCOUNT_SERVICE_UNAVAILABLE", "账号服务暂时不可用，请稍后再试", 503
    )


def _badRequest(message: str = "请求参数不合法") -> AccountServiceError:
    return AccountServiceError("BAD_REQUEST", message, 400)


def _raiseForAcis(errCode: str, scene: str) -> None:
    """把 acis 错误码映射成业务异常（调用方只知道「失败」，不知道具体原因）。

    scene 只影响少数需要「对外隐藏」的分支：
      login   —— 一律 ACCOUNT_AUTH_FAILED，不泄露账号是否存在；
      reset   —— 验证码/账号问题一律 VERIFY_CODE_INVALID，避免手机号枚举。
    """
    if errCode == ERR_SVC_OFFLINE:
        raise _svcUnavailable()

    code = ERR_CODE_MAP.get(errCode, "BAD_REQUEST")

    if scene == "login":
        raise AccountServiceError("ACCOUNT_AUTH_FAILED", "账号或密码不正确", 401)

    if scene == "reset" and code in (
        "VERIFY_CODE_INVALID",
        "ACCOUNT_LOGIN_ID_INVALID",
        "ACCOUNT_AUTH_FAILED",
        "ACCOUNT_REGISTER_DISABLED",  # BE: acis A9A0 用 BE 表示账号不存在
    ):
        raise AccountServiceError("VERIFY_CODE_INVALID", "验证码不正确或已失效", 400)

    raise AccountServiceError(code, _messageOf(code), _httpStatusOf(code))


def _messageOf(code: str) -> str:
    return {
        "ACCOUNT_AUTH_FAILED": "账号或密码不正确",
        "UNAUTHORIZED": "登录已失效，请重新登录",
        "ACCOUNT_LOGIN_ID_EXISTS": "这个账号已经注册过了",
        "ACCOUNT_LOGIN_ID_INVALID": "请输入正确的手机号",
        "ACCOUNT_REGISTER_DISABLED": "注册功能未开放",
        "PASSWORD_RESET_DISABLED": "自助找回密码已关闭",
        "PASSWORD_REUSED": "新密码不能和原密码一样",
        "VERIFY_CODE_REQUIRED": "请先获取验证码",
        "VERIFY_CODE_INVALID": "验证码不正确或已失效",
        "VERIFY_CODE_ATTEMPTS_EXCEEDED": "验证码错误次数过多，请重新获取",
        "VERIFY_CODE_SEND_TOO_FAST": "验证码发送过于频繁，请稍后再试",
        "VERIFY_CODE_SEND_FAILED": "验证码发送失败，请稍后再试",
        "PASSWORD_TOO_SHORT": "密码长度不能少于 6 位",
    }.get(code, "请求参数不合法")


def _httpStatusOf(code: str) -> int:
    return {
        "UNAUTHORIZED": 401,
        "ACCOUNT_LOGIN_ID_EXISTS": 409,
        "ACCOUNT_REGISTER_DISABLED": 403,
        "PASSWORD_RESET_DISABLED": 403,
        "VERIFY_CODE_SEND_TOO_FAST": 429,
        "VERIFY_CODE_SEND_FAILED": 502,
        "VERIFY_CODE_ATTEMPTS_EXCEEDED": 429,
    }.get(code, 400)


# ---------------------------------------------------------------- 角色映射


def systemRoleOf(acisRoleName: str) -> str:
    """acis roleName -> 本系统角色（01 §5.5）。"""
    return ROLE_ADMIN if (acisRoleName or "") in USER_ADMIN_ROLE_LIST else ROLE_MEMBER


def acisRoleOf(systemRole: str) -> str:
    """本系统角色 -> acis roleName（回写 acis 用；不可映射时回落默认角色）。"""
    return ROLE_ACCOUNT_ROLE.get(systemRole) or ROLE_ACCOUNT_ROLE.get(ROLE_MEMBER, "customer")


def defaultSystemRole() -> str:
    role = (settings.account_default_role or ROLE_MEMBER).strip().lower()
    return role if role in (ROLE_ADMIN, ROLE_MEMBER) else ROLE_MEMBER


# ---------------------------------------------------------------- 验证码本地限流


class _VerifyCodeGuard:
    """进程内限流计数（04 §2.3）：60 秒冷却 + 连续 5 次失败锁定。

    只保存「上次发送时间 / 是否发过 / 失败次数」，不保存验证码本身；
    单进程（--workers 1），重启清零，不做跨实例共享。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, dict[str, float]] = {}

    @staticmethod
    def _key(scene: str, loginID: str) -> str:
        return f"{scene}:{loginID}"

    def _entry(self, key: str) -> dict[str, float]:
        return self._state.setdefault(key, {"sentAt": 0.0, "attempts": 0.0})

    def cooldownRemaining(self, scene: str, loginID: str) -> int:
        cooldown = max(0, int(settings.auth_verify_code_cooldown_seconds))
        with self._lock:
            sentAt = self._entry(self._key(scene, loginID)).get("sentAt", 0.0)
        if sentAt <= 0 or cooldown <= 0:
            return 0
        remaining = cooldown - int(time.time() - sentAt)
        return max(0, remaining)

    def markSent(self, scene: str, loginID: str) -> None:
        with self._lock:
            self._pruneIfNeeded()
            entry = self._entry(self._key(scene, loginID))
            entry["sentAt"] = time.time()
            entry["attempts"] = 0.0

    def _pruneIfNeeded(self) -> None:
        """进程内计数不能无限增长：超过 5000 个 key 时清掉一天前的记录。"""
        if len(self._state) <= 5000:
            return
        expiredBefore = time.time() - 86400
        for key in [k for k, v in self._state.items() if v.get("sentAt", 0.0) < expiredBefore]:
            self._state.pop(key, None)

    def hasPendingCode(self, scene: str, loginID: str) -> bool:
        with self._lock:
            sentAt = self._entry(self._key(scene, loginID)).get("sentAt", 0.0)
        if sentAt <= 0:
            return False
        return (time.time() - sentAt) <= VERIFY_CODE_EXPIRE_SECONDS

    def ensureNotLocked(self, scene: str, loginID: str) -> None:
        with self._lock:
            attempts = self._entry(self._key(scene, loginID)).get("attempts", 0.0)
        if attempts >= max(1, int(settings.auth_verify_code_max_attempts)):
            raise AccountServiceError(
                "VERIFY_CODE_ATTEMPTS_EXCEEDED",
                "验证码错误次数过多，请重新获取",
                429,
            )

    def recordFailure(self, scene: str, loginID: str) -> None:
        with self._lock:
            entry = self._entry(self._key(scene, loginID))
            entry["attempts"] = entry.get("attempts", 0.0) + 1.0
            attempts = entry["attempts"]
        if attempts >= max(1, int(settings.auth_verify_code_max_attempts)):
            raise AccountServiceError(
                "VERIFY_CODE_ATTEMPTS_EXCEEDED",
                "验证码错误次数过多，请重新获取",
                429,
            )

    def clear(self, scene: str, loginID: str) -> None:
        with self._lock:
            self._state.pop(self._key(scene, loginID), None)

    def resetAll(self) -> None:
        with self._lock:
            self._state.clear()


verifyCodeGuard = _VerifyCodeGuard()

# acis 会话缓存：仅用于 A5A0 登出与 A2A0 改密（JWT 不放 sessionID）。
# 进程内、非持久、重启失效；失效后改密会重新走一次 A0A0 拿新会话。
_sessionCache: dict[str, str] = {}
_sessionLock = threading.Lock()


def _rememberSession(loginID: str, sessionID: str) -> None:
    if not loginID or not sessionID:
        return
    with _sessionLock:
        _sessionCache[loginID] = sessionID


def _popSession(loginID: str) -> str:
    with _sessionLock:
        return _sessionCache.pop(loginID, "")


def _peekSession(loginID: str) -> str:
    with _sessionLock:
        return _sessionCache.get(loginID, "")


# ---------------------------------------------------------------- 档案映射与同步


def _acisProfileToColumns(rtnData: dict, systemRole: str | None = None) -> dict:
    """A3A0 回包 -> USER_BASIC 列（只取存在的列，值一律字符串）。"""
    acisRoleName = (rtnData.get("roleName") or "").strip()
    if not acisRoleName and systemRole:
        acisRoleName = acisRoleOf(systemRole)

    def text(key: str) -> str:
        value = rtnData.get(key, "")
        return "" if value is None else str(value).strip()

    profile = {
        "openID": text("openID") or text("regOpenID"),
        "roleName": acisRoleName,
        "nickName": text("nickName"),
        "realName": text("realName"),
        # 02 §3.1：USER_BASIC 列名为 gender，acis 可能回 sex
        "gender": text("gender") or text("sex"),
        "avatarID": text("avatarID"),
        "mobilePhoneNo": text("mobilePhoneNo"),
        "province": text("province"),
        "city": text("city"),
        "area": text("area"),
        "address": text("address"),
        "email": text("email"),
        "PID": text("PID"),
        "photoIDFront": text("photoIDFront"),
        "photoIDBack": text("photoIDBack"),
        "photoID": text("photoID"),
        "activeFlag": text("activeFlag") or "1",
    }
    return {key: value for key, value in profile.items() if key in _PROFILE_COLUMNS}


def syncUserBasic(
    loginID: str,
    profile: dict,
    passwdHash: str = "",
    operatorLoginID: str = "",
) -> str:
    """把 acis 档案同步进 USER_BASIC（contentHub writeUser2UserBasic 的本项目版本）。

    出参："inserted" / "updated" / "unchanged"。
      - 已存在：只写差异列；无差异时**不执行 UPDATE**（含 updateYMDHMS）；
      - 不存在：插入并写 regID/regYMDHMS/regPosition（44 列结构不变）；
      - passwd 仅在注册/找回成功后按 md5 镜像写入，不参与任何校验。
    """
    loginID = normalizeLoginID(loginID)
    if not loginID:
        raise _badRequest("缺少登录号")

    rows = mysqlCommon.queryUserBasic(loginID, mode="full")
    now = misc.getTime()

    if len(rows) == 1:
        current = rows[0]
        diff: dict[str, Any] = {}
        for column, value in profile.items():
            if value == "" or value is None:
                # updateUserBasic 对空值一律跳过，这里提前过滤，避免误判为「有变化」
                continue
            if column == "nickName" and str(current.get("nickName") or "").strip():
                # 昵称以本地为准：owner/admin 可在「家庭成员」里代改成员昵称，
                # 账号服务回包的昵称只在首次建档时落地，不能把本地改过的值覆盖回去
                continue
            if str(current.get(column) or "") != str(value):
                diff[column] = value
        if not diff:
            return "unchanged"
        diff["updateYMDHMS"] = now
        mysqlCommon.updateUserBasic(loginID, diff)
        return "updated"

    dataSet = {key: value for key, value in profile.items()}
    dataSet.setdefault("regID", operatorLoginID or loginID)
    dataSet["regYMDHMS"] = now
    # regPosition 是 JSON 列（02 §5）：写 {"scene":"web"}，由 insertUserBasic 归一化
    dataSet["regPosition"] = {"scene": "web"}
    dataSet.setdefault("activeFlag", "1")
    dataSet.setdefault("delFlag", "0")
    if passwdHash:
        dataSet["passwd"] = passwdHash
        dataSet["passwdYMDHMS"] = now
    mysqlCommon.insertUserBasic(loginID, dataSet)
    return "inserted"


def _syncPasswdMirror(loginID: str, passwdHash: str) -> bool:
    """找回口令/改密后只回写 passwd + passwdYMDHMS 镜像（04 §2.2、01 §5.5）。

    账号不存在（USER_BASIC 无行）时什么都不写，避免凭空建档。
    """
    if not loginID or not passwdHash:
        return False
    rows = mysqlCommon.queryUserBasic(loginID, mode="full")
    if len(rows) != 1:
        return False
    mysqlCommon.updateUserBasic(
        loginID, {"passwd": passwdHash, "passwdYMDHMS": misc.getTime()}
    )
    return True


def loadUserRow(loginID: str) -> dict:
    """读 USER_BASIC 单行（deps / 摘要用）；不存在返回 {}。"""
    loginID = normalizeLoginID(loginID)
    if not loginID:
        return {}
    rows = mysqlCommon.queryUserBasic(loginID, mode="full")
    if len(rows) != 1:
        return {}
    return rows[0]


def ensureUserBasic(loginID: str, operatorLoginID: str = "") -> str:
    """确保账号有 USER_BASIC 档案（S4 添加家庭成员时调用，04 §3）。

    出参："exists" / "inserted"。

    为什么不做 A3A0：acis 的 A3A0 依赖**目标用户自己的会话**（sessionIDSet 按 loginID），
    无法由他人代取。这里只补一条最小档案，昵称等资料在该用户下次登录时由
    `syncUserBasic` 补齐；不写 passwd 镜像，避免制造无效凭据。
    """
    loginID = normalizeLoginID(loginID)
    if not loginID:
        return "exists"
    if loadUserRow(loginID):
        return "exists"

    now = misc.getTime()
    dataSet = {
        "nickName": "",
        "roleName": acisRoleOf(defaultSystemRole()),
        "activeFlag": "1",
        "regPosition": {"scene": "web"},
        "regID": operatorLoginID or loginID,
        "regYMDHMS": now,
        "delFlag": "0",
    }
    mysqlCommon.insertUserBasic(loginID, dataSet)
    return "inserted"


def updateNickName(loginID: str, nickName: str, operatorLoginID: str = "") -> bool:
    """本地改昵称（家庭 owner/admin 代改成员昵称）：只写 `USER_BASIC.nickName`。

    为什么不去账号服务改：acis 的 A2A0 需要**目标用户自己的会话**，管理员无法代改。
    因此昵称以本地档案为准（`syncUserBasic` 不再用 acis 回包覆盖已有的昵称）。
    出参：True 写入成功；False 账号无档案或写库失败（调用方按 500 处理）。
    """
    loginID = normalizeLoginID(loginID)
    if not loginID or not nickName:
        return False
    rows = mysqlCommon.queryUserBasic(loginID, mode="full")
    if len(rows) != 1:
        return False
    affected = mysqlCommon.updateUserBasic(
        loginID,
        {
            "nickName": nickName,
            "modifyID": operatorLoginID or loginID,
            "modifyYMDHMS": misc.getTime(),
        },
    )
    return affected > 0


def publicUser(row: dict, systemRole: str) -> dict:
    """04 §2 的 user 摘要（不含 passwd 等敏感列）。"""
    return {
        "login_id": row.get("loginID", ""),
        "nick_name": row.get("nickName", "") or row.get("loginID", ""),
        "avatar_id": row.get("avatarID", ""),
        "role_name": row.get("roleName", ""),
        "role": systemRole,
        "active_flag": row.get("activeFlag", "") or "1",
    }


# ---------------------------------------------------------------- 登录 / 登出


def login(loginID: str, passwd: str) -> dict:
    """A0A0 登录 -> A3A0 取资料 -> USER_BASIC upsert -> 返回用户摘要与角色。

    出参: {"login_id","role","role_name","nick_name","avatar_id","active_flag","profile"}
    """
    loginID = normalizeLoginID(loginID)
    if not loginID or not passwd:
        raise AccountServiceError("ACCOUNT_AUTH_FAILED", "账号或密码不正确", 401)

    errCode, rtnData = accountClient.forward(
        accountClient.ACCOUNT_SVC_CMD_LOGIN,
        {"loginID": loginID, "passwd": hashPasswd(passwd, loginID)},
    )
    if errCode != ERR_OK:
        _raiseForAcis(errCode, "login")

    sessionID = str(rtnData.get("sessionID") or "")
    acisRoleName = str(rtnData.get("roleName") or "")
    systemRole = systemRoleOf(acisRoleName) if acisRoleName else defaultSystemRole()

    profileData = accountClient.getUserInfo(loginID, sessionID)
    if not profileData:
        # A3A0 取不到资料：视为账号服务异常，宁可不登录也不写半条档案（01 §5.5-5）
        logger.error("A3A0 取资料失败，登录中止 loginID=%s", loginID)
        raise _svcUnavailable()

    profile = _acisProfileToColumns(profileData, systemRole)
    if profile.get("activeFlag") == "0":
        raise AccountServiceError("FORBIDDEN", "该账号已被停用", 403)

    # 档案里的 acis 角色优先（A3A0 回包通常不带 roleName，此时沿用 A0A0 的）
    if profile.get("roleName"):
        systemRole = systemRoleOf(profile["roleName"])

    syncUserBasic(loginID, profile)
    row = loadUserRow(loginID)
    if not row:
        # 档案没落库就不签 token：宁可登录失败，也不产生「有 JWT 没档案」的半登录态
        logger.error("USER_BASIC 同步后仍查不到记录，登录中止 loginID=%s", loginID)
        raise AccountServiceError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)

    _rememberSession(loginID, sessionID)
    return {
        **publicUser(row, systemRole),
        "login_id": loginID,
        "role": systemRole,
        "role_name": profile.get("roleName", "") or acisRoleName,
        "nick_name": row.get("nickName", "") or loginID,
        "avatar_id": row.get("avatarID", ""),
        "active_flag": row.get("activeFlag", "") or "1",
    }


def logout(loginID: str) -> None:
    """A5A0 登出（尽力而为）：账号服务不可达不影响本地返回（01 §5.5-11）。"""
    loginID = normalizeLoginID(loginID)
    sessionID = _popSession(loginID)
    if not loginID or not sessionID:
        # 没有 acis 会话（进程重启/未登录过账号服务）：只丢本地态，不触达账号服务
        return
    try:
        errCode, _ = accountClient.forward(
            accountClient.ACCOUNT_SVC_CMD_LOGOUT, {"sessionID": sessionID}
        )
        if errCode != ERR_OK:
            logger.info("A5A0 登出未成功（忽略） loginID=%s errCode=%s", loginID, errCode)
    except Exception as error:  # noqa: BLE001 登出绝不因下游异常而失败
        logger.warning("A5A0 登出异常（忽略） loginID=%s err=%s", loginID, error)


# ---------------------------------------------------------------- 注册 / 验证码


def sendVerifyCode(loginID: str, scene: str) -> dict:
    """A6A0 发码。出参 {"ok":True,"cooldown_seconds":n,"expire_seconds":600}。"""
    loginID = normalizeLoginID(loginID)
    scene = (scene or "").strip()

    if scene not in SCENE_LIST:
        raise _badRequest("scene 只支持 register / reset_password")
    if scene == SCENE_REGISTER and not settings.account_register_enabled:
        raise AccountServiceError("ACCOUNT_REGISTER_DISABLED", "注册功能未开放", 403)
    if scene == SCENE_RESET and not settings.account_password_reset_enabled:
        raise AccountServiceError("PASSWORD_RESET_DISABLED", "自助找回密码已关闭", 403)
    if not _validLoginID(loginID):
        raise AccountServiceError("ACCOUNT_LOGIN_ID_INVALID", "请输入正确的手机号", 400)

    remaining = verifyCodeGuard.cooldownRemaining(scene, loginID)
    if remaining > 0:
        raise AccountServiceError(
            "VERIFY_CODE_SEND_TOO_FAST",
            f"验证码发送过于频繁，请 {remaining} 秒后再试",
            429,
        )

    errCode, _ = accountClient.forward(
        accountClient.ACCOUNT_SVC_CMD_SMS_REQUEST, {"loginID": loginID, "lang": "CN"}
    )

    if errCode == ERR_SVC_OFFLINE:
        raise _svcUnavailable()

    if scene == SCENE_RESET and errCode in ("B1", "BE", "BW"):
        # 账号不存在/号码无效：对外仍返回 ok，只在审计日志留痕（04 §2.2-2）
        logger.info("A6A0 找回口令发码被忽略 loginID=%s errCode=%s", loginID, errCode)
        return {
            "ok": True,
            "cooldown_seconds": 0,
            "expire_seconds": VERIFY_CODE_EXPIRE_SECONDS,
        }

    if errCode == "CS":
        raise AccountServiceError(
            "VERIFY_CODE_SEND_TOO_FAST", "验证码发送过于频繁，请稍后再试", 429
        )
    if errCode == "BN":
        raise AccountServiceError(
            "VERIFY_CODE_SEND_FAILED", "验证码发送失败，请稍后再试", 502
        )
    if errCode == "BW":
        raise AccountServiceError("ACCOUNT_LOGIN_ID_INVALID", "请输入正确的手机号", 400)
    if errCode != ERR_OK:
        _raiseForAcis(errCode, "register")

    verifyCodeGuard.markSent(scene, loginID)
    return {
        "ok": True,
        "cooldown_seconds": max(0, int(settings.auth_verify_code_cooldown_seconds)),
        "expire_seconds": VERIFY_CODE_EXPIRE_SECONDS,
    }


def register(loginID: str, passwd: str, verifyCode: str, nickName: str = "") -> dict:
    """A0A0(注册) -> A3A0 -> USER_BASIC insert。**不签发 JWT**（04 §2.1-6）。"""
    loginID = normalizeLoginID(loginID)

    # 开关关闭时先拒，保证「账号服务零调用」
    if not settings.account_register_enabled:
        raise AccountServiceError("ACCOUNT_REGISTER_DISABLED", "注册功能未开放", 403)

    if not _validLoginID(loginID):
        raise AccountServiceError("ACCOUNT_LOGIN_ID_INVALID", "请输入正确的手机号", 400)
    _validatePasswd(passwd)
    _validateVerifyCode(verifyCode)

    nickName = (nickName or "").strip()
    if len(nickName) > 20:
        raise AccountServiceError("BAD_REQUEST", "昵称最多 20 字", 400)

    if not verifyCodeGuard.hasPendingCode(SCENE_REGISTER, loginID):
        raise AccountServiceError("VERIFY_CODE_REQUIRED", "请先获取验证码", 400)
    verifyCodeGuard.ensureNotLocked(SCENE_REGISTER, loginID)

    # acis 的 A0A0 对「已存在的账号 + 正确口令」按登录处理（回 B0），不会回 B4；
    # 注册语义下先用 AIA0 判重，才能给出 04 §10 约定的 ACCOUNT_LOGIN_ID_EXISTS。
    if accountClient.chkUserExist(loginID):
        raise AccountServiceError("ACCOUNT_LOGIN_ID_EXISTS", "这个账号已经注册过了", 409)

    passwdHash = hashPasswd(passwd, loginID)
    errCode, rtnData = accountClient.forward(
        accountClient.ACCOUNT_SVC_CMD_LOGIN,
        {
            "loginID": loginID,
            "passwd": passwdHash,
            "verifyCode": (verifyCode or "").strip(),
            "nickName": (nickName or "").strip(),
        },
    )

    if errCode == ERR_SVC_OFFLINE:
        raise _svcUnavailable()
    if errCode == "BM":
        verifyCodeGuard.recordFailure(SCENE_REGISTER, loginID)
        raise AccountServiceError("VERIFY_CODE_INVALID", "验证码不正确或已失效", 400)
    if errCode == "B4":
        raise AccountServiceError("ACCOUNT_LOGIN_ID_EXISTS", "这个账号已经注册过了", 409)
    if errCode in ("BE", "BS"):
        raise AccountServiceError("ACCOUNT_REGISTER_DISABLED", "注册功能未开放", 403)
    if errCode in ("BW", "B7"):
        raise AccountServiceError("ACCOUNT_LOGIN_ID_INVALID", "请输入正确的手机号", 400)
    if errCode in ("B1", "B3", "B5"):
        # 并发注册时 A0A0 可能按「账号已存在」处理并回口令类错误码
        raise AccountServiceError("ACCOUNT_LOGIN_ID_EXISTS", "这个账号已经注册过了", 409)
    if errCode != ERR_OK:
        _raiseForAcis(errCode, "register")

    verifyCodeGuard.clear(SCENE_REGISTER, loginID)

    # 注册回包不含资料明细；用 A0A0 的会话取一次 A3A0，失败不阻断（账号已建好）
    sessionID = str(rtnData.get("sessionID") or "")
    profileData = accountClient.getUserInfo(loginID, sessionID)
    if profileData:
        systemRole = systemRoleOf(str(rtnData.get("roleName") or ""))
        syncUserBasic(
            loginID,
            _acisProfileToColumns(profileData, systemRole),
            passwdHash=passwdHash,
            operatorLoginID=loginID,
        )
    else:
        logger.warning("注册成功但 A3A0 取资料失败，USER_BASIC 待首次登录补写 loginID=%s", loginID)

    return {"ok": True, "login_id": loginID}


def resetPassword(loginID: str, verifyCode: str, newPasswd: str) -> dict:
    """A9A0 凭验证码重置口令；成功后只回写 passwd/passwdYMDHMS 镜像。"""
    loginID = normalizeLoginID(loginID)

    if not settings.account_password_reset_enabled:
        raise AccountServiceError("PASSWORD_RESET_DISABLED", "自助找回密码已关闭", 403)

    if not _validLoginID(loginID):
        raise AccountServiceError("ACCOUNT_LOGIN_ID_INVALID", "请输入正确的手机号", 400)
    _validatePasswd(newPasswd)
    _validateVerifyCode(verifyCode)

    if not verifyCodeGuard.hasPendingCode(SCENE_RESET, loginID):
        raise AccountServiceError("VERIFY_CODE_REQUIRED", "请先获取验证码", 400)
    verifyCodeGuard.ensureNotLocked(SCENE_RESET, loginID)

    passwdHash = hashPasswd(newPasswd, loginID)
    errCode, _ = accountClient.forward(
        accountClient.ACCOUNT_SVC_CMD_RESET_PASSWD,
        {
            "loginID": loginID,
            "passwd": passwdHash,
            "verifyCode": (verifyCode or "").strip(),
        },
    )

    if errCode == ERR_SVC_OFFLINE:
        raise _svcUnavailable()
    if errCode == "BM":
        verifyCodeGuard.recordFailure(SCENE_RESET, loginID)
        raise AccountServiceError("VERIFY_CODE_INVALID", "验证码不正确或已失效", 400)
    if errCode == "B3":
        raise AccountServiceError("PASSWORD_TOO_SHORT", "密码长度不能少于 6 位", 400)
    if errCode != ERR_OK:
        _raiseForAcis(errCode, "reset")

    verifyCodeGuard.clear(SCENE_RESET, loginID)
    _syncPasswdMirror(loginID, passwdHash)
    # 口令已变更：旧 acis 会话不可再用于登出/改密
    _popSession(loginID)

    return {"ok": True}


# ---------------------------------------------------------------- 登录态改密


def changePassword(loginID: str, oldPasswd: str, newPasswd: str) -> dict:
    """登录态改密：先用 A0A0 验证旧口令（本地不校验），再用 A2A0 写新口令。

    说明（与 04 §2.5 的差异，已在交付说明中登记）：
      acis 的 A9A0 是「凭短信验证码重置口令」，不接受 sessionID + 旧口令；
      登录态改密在 acis 侧对应 A2A0 的 newPasswd 分支（需会话上下文）。
      因此这里重新登录取一次会话，再调 A2A0。
    """
    loginID = normalizeLoginID(loginID)

    if not loginID or not oldPasswd or not newPasswd:
        raise _badRequest("原密码和新密码都要填")
    _validatePasswd(newPasswd)
    if oldPasswd == newPasswd:
        raise AccountServiceError("PASSWORD_REUSED", "新密码不能和原密码一样", 400)

    # 1) 用旧口令走一次 A0A0：口令校验完全交给账号服务
    errCode, rtnData = accountClient.forward(
        accountClient.ACCOUNT_SVC_CMD_LOGIN,
        {"loginID": loginID, "passwd": hashPasswd(oldPasswd, loginID)},
    )
    if errCode != ERR_OK:
        _raiseForAcis(errCode, "login")

    sessionID = str(rtnData.get("sessionID") or "") or _peekSession(loginID)
    if not sessionID:
        raise _svcUnavailable()

    # 2) A2A0 修改口令（newPasswd 走同一 md5 口径）
    newHash = hashPasswd(newPasswd, loginID)
    errCode, _ = accountClient.forward(
        accountClient.ACCOUNT_SVC_CMD_MODIFY_USER,
        {"loginID": loginID, "sessionID": sessionID, "newPasswd": newHash},
    )
    if errCode == ERR_SVC_OFFLINE:
        raise _svcUnavailable()
    if errCode == "B8":
        raise AccountServiceError("UNAUTHORIZED", "登录已失效，请重新登录", 401)
    if errCode != ERR_OK:
        _raiseForAcis(errCode, "change")

    _rememberSession(loginID, sessionID)
    _syncPasswdMirror(loginID, newHash)
    return {"ok": True}


# ---------------------------------------------------------------- 对外开关


def options() -> dict:
    """GET /api/auth/options：两个开关与冷却秒数（前端不硬编码，04 §2）。"""
    return {
        "register_enabled": settings.account_register_enabled,
        "password_reset_enabled": settings.account_password_reset_enabled,
        "verify_code_cooldown_seconds": max(
            0, int(settings.auth_verify_code_cooldown_seconds)
        ),
    }


def checkService() -> tuple[bool, str]:
    """启动探活（不阻塞启动）：出参 (可达, 说明)。"""
    return accountClient.ping()
