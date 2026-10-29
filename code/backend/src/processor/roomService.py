"""房间域服务：开桌 / 房间列表 / 入房校验 / 关房 / 聊天记录（04 §6）。

职责边界（01 §2）：
  - 路由只解析参数、调本模块、套响应模型；
  - 本模块负责房间归属解析（按房间自身的 familyID，不信查询参数）、模板可见性与族就绪校验、
    邀请码生成、事务与错误码；开桌与房间列表仍限本家庭成员，入房相关读接口凭邀请码可跨家庭；
  - 房态（座位、在线连接、观战绑定）只在内存 `realtime.room_manager`，**不落库**，
    因此 `player_count` / `spectator_count` 由路由从 actor 取实时值传入。

事务口径（01 §7.4）：开桌是一个业务动作，先校验后写库；校验失败时 `mj_room` 不留半条记录。
"""

from __future__ import annotations

import secrets

from common import miscCommon as misc
from common import mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from config.localSettings import settings
from game.families import registry
from processor import familyService, ruleService
from schemas.rule import RuleConfig

logger = get_logger("mahjong.room")

ROOM_OPEN = "OPEN"
ROOM_CLOSED = "CLOSED"

# 邀请码：6 位数字，首位非 0（04 §6）；全局唯一，冲突重试 10 次
ROOM_CODE_MIN = 100000
ROOM_CODE_RANGE = 900000
ROOM_CODE_RETRY = 10

# 观战（S5b / 04 §9.1）：每座 10 人、全房 40 人、断线保留 60 秒（config/basicSettings）
SPECTATE_LIMIT_PER_SEAT = settings.spectate_limit_per_seat
SPECTATE_LIMIT_ROOM = settings.spectate_room_max

MAX_ROOM_LIMIT = 20
MAX_MESSAGE_LIMIT = 200


class RoomServiceError(BizError):
    """房间域业务异常（HTTP 状态 + 错误码 + 中文提示）。"""


# ---------------------------------------------------------------- 小工具


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _iso(ymdhms: str) -> str:
    return misc.ymdhmsToIso(ymdhms)


def _err(code: str, message: str, httpStatus: int = 400) -> RoomServiceError:
    return RoomServiceError(code, message, httpStatus)


def _randomRoomCode() -> str:
    return str(ROOM_CODE_MIN + secrets.randbelow(ROOM_CODE_RANGE))


def ruleConfigOf(row: dict) -> RuleConfig:
    """从房间/场次快照恢复规则（快照结构：{rule_family_code, engine_code, config, ...}）。

    - 按快照里的 `rule_family_code` 取该族的配置模型（03 §11：前端只读快照、不反推模板）；
    - 兼容 S5 之前的旧快照（直接就是 RuleConfig 的字段），旧数据不会让牌桌打不开；
    - 已作废的 `dealer_continue_on_win/draw` 由模型加载时忽略并记 warning。
    """
    snapshot = row.get("ruleSnapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    config = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else snapshot
    ruleFamilyCode = str(snapshot.get("rule_family_code") or row.get("ruleFamilyCode") or "generic")
    try:
        model = registry.config_model_of(ruleFamilyCode)
    except registry.FamilyError:
        # 族已下线但历史房间还要能打开：退回通用族模型读同一份 JSON
        model = RuleConfig
    return model.model_validate(config or {})


def roomOut(row: dict, playerCount: int = 0, spectatorCount: int = 0, familyCode: str = "") -> dict:
    """04 §6 的 room 结构。"""
    templateID = int(row.get("templateID") or 0)
    return {
        "id": int(row.get("recID") or 0),
        "room_code": _text(row, "roomCode"),
        "family_code": familyCode,
        "room_name": _text(row, "roomName"),
        "host_login_id": _text(row, "hostLoginID"),
        "host_name": _text(row, "hostName") or _text(row, "hostLoginID"),
        "template_id": templateID or None,
        "rule_name": _text(row, "templateName") or "自定义规则",
        "rule_family_code": _text(row, "ruleFamilyCode"),
        "status": _text(row, "roomStatus") or ROOM_OPEN,
        "player_count": int(playerCount or 0),
        "spectator_count": int(spectatorCount or 0),
        "created_at": _iso(_text(row, "createdYMDHMS")),
    }


def joinCheckOut(row: dict, playerCount: int = 0, viewerCounts: list[int] | None = None,
                 needsApproval: bool = False) -> dict:
    """04 §6 的 room_join_check 结构。

    `viewer_counts` 来自内存房态（`RoomActor.spectator_counts`）；`available=false`
    表示 4 座已满且 40 个观战位全满，前端据此禁用「进入观战」。
    `needs_approval=true`：呼叫者不是本家庭成员，进桌要房主在牌桌上确认。
    """
    status = _text(row, "roomStatus") or ROOM_OPEN
    players = int(playerCount or 0)
    rawCounts = list(viewerCounts or [])
    counts = [int(rawCounts[index]) if index < len(rawCounts) else 0 for index in range(4)]
    occupied = sum(counts)
    available = status == ROOM_OPEN and not (players >= 4 and occupied >= SPECTATE_LIMIT_ROOM)
    return {
        "room_code": _text(row, "roomCode"),
        "room_name": _text(row, "roomName"),
        "host_name": _text(row, "hostName") or _text(row, "hostLoginID"),
        "rule_name": _text(row, "templateName") or "自定义规则",
        "rule_family_code": _text(row, "ruleFamilyCode"),
        "status": status,
        "player_count": players,
        "can_join": status == ROOM_OPEN and players < 4,
        "needs_approval": bool(needsApproval),
        "spectate": {
            "limit_per_seat": SPECTATE_LIMIT_PER_SEAT,
            "viewer_counts": counts,
            "available": available,
        },
    }


def messageOut(row: dict) -> dict:
    """04 §9.4 的 chat.message 结构（REST 与 WS 共用）。"""
    loginID = _text(row, "loginID")
    return {
        "id": int(row.get("recID") or 0),
        "room_id": int(row.get("roomID") or 0),
        "login_id": loginID or None,
        "user_name": _text(row, "userName") or (loginID or "系统"),
        "kind": _text(row, "messageKind") or "chat",
        "content": _text(row, "content"),
        "created_at": _iso(_text(row, "createdYMDHMS")),
    }


# ---------------------------------------------------------------- 读取


def _assertMember(loginID: str, familyID: int, requireEnabled: bool = False) -> dict:
    return familyService.assertMemberOfFamilyID(
        loginID, familyID, requireEnabled=requireEnabled
    )


def _roomFamilyContext(
    loginID: str, familyID: int, requireEnabled: bool = False
) -> tuple[dict, bool]:
    """房间归属家庭的上下文 + 呼叫者是否该家庭成员。

    入房口径（S9）：房间仍然属于原家庭（列表/战绩/落库一律按房间 familyID），
    但**邀请码本身就是入场凭证**——非本家庭的登录用户凭码也能读房间与进桌，
    因此这里不再强制成员关系，只把 `memberRole` 置空（家庭管理员类操作会被拒绝）。
    家庭停用（requireEnabled=True）时整房拒绝，与成员口径一致；
    家庭被物理删除的房间视为不可用，避免留下无法治理的孤儿房。
    """
    fid = int(familyID or 0)
    family = mysqlCommon.query_mj_family_by_id(fid) if fid > 0 else {}
    if not family:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)

    familyStatus = _text(family, "familyStatus") or familyService.FAMILY_ENABLED
    if requireEnabled and familyStatus != familyService.FAMILY_ENABLED:
        raise familyService.FamilyServiceError("FAMILY_DISABLED", "该家庭已停用", 403)

    member = mysqlCommon.query_mj_family_member(fid, loginID) if loginID else {}
    isMember = bool(member) and _text(member, "memberStatus") == familyService.STATUS_ACTIVE
    context = {
        "familyID": fid,
        "familyCode": _text(family, "familyCode"),
        "memberRole": _text(member, "memberRole") if isMember else "",
        "familyStatus": familyStatus,
        "family": family,
    }
    return context, isMember


def _loadRoom(roomID: int) -> dict:
    row = mysqlCommon.query_mj_room_by_id(roomID)
    if not row:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)
    return row


def listRooms(loginID: str, familyID: int, familyCode: str, limit: int = MAX_ROOM_LIMIT,
              beforeID: int = 0) -> list[dict]:
    """家庭房间列表：只列 OPEN，recID 倒序（04 §6 #26）。"""
    _assertMember(loginID, familyID, requireEnabled=True)
    rows = mysqlCommon.query_mj_room_list(familyID, limit=limit, beforeID=beforeID)
    return [roomOut(row, familyCode=familyCode) for row in rows]


def getRoom(loginID: str, roomID: int, playerCount: int = 0, spectatorCount: int = 0) -> dict:
    """房间详情（04 §6 #27）：以房间自身 familyID 校验成员关系。

    按 `room_id` 自增枚举就能读到 room_code，会绕过邀请码的随机性，因此这里不放开；
    跨家庭进入只走「凭码」的两条路径（`getRoomByCode` / WS 握手）。
    """
    row = _loadRoom(roomID)
    context = _assertMember(loginID, int(row.get("familyID") or 0))
    return roomOut(
        row,
        playerCount=playerCount,
        spectatorCount=spectatorCount,
        familyCode=context.get("familyCode", ""),
    )


def getRoomByCode(
    loginID: str,
    roomCode: str,
    playerCount: int = 0,
    viewerCounts: list[int] | None = None,
) -> dict:
    """按邀请码入房校验（04 §6 #28）：格式 → 存在 → 家庭可用 → 状态。

    S9：邀请码即入场凭证，非本家庭登录用户同样可校验通过（不再返回 403）。
    """
    code = (roomCode or "").strip()
    if len(code) != 6 or not code.isdigit() or code[0] == "0":
        raise _err("INVITE_CODE_FORMAT", "邀请码必须是 6 位数字")
    row = mysqlCommon.query_mj_room_by_code(code)
    if not row:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)
    _context, isMember = _roomFamilyContext(loginID, int(row.get("familyID") or 0))
    if _text(row, "roomStatus") == ROOM_CLOSED:
        raise _err("ROOM_CLOSED", "房间已经关闭了")
    needsApproval = not isMember and _text(row, "hostLoginID") != loginID
    return joinCheckOut(
        row, playerCount=playerCount, viewerCounts=viewerCounts, needsApproval=needsApproval
    )


def listMessages(loginID: str, roomID: int, limit: int = 50) -> list[dict]:
    """最近聊天（04 §6 #30）：必带 LIMIT，返回按时间正序。

    与 `getRoom` 同理保持成员校验：跨家庭玩家进桌后的聊天走 WS 的 `room.welcome`，
    不需要按 room_id 读历史。
    """
    row = _loadRoom(roomID)
    _assertMember(loginID, int(row.get("familyID") or 0))
    rows = mysqlCommon.query_mj_room_message_list(roomID, limit=limit)
    rows.reverse()
    return [messageOut(item) for item in rows]


# ---------------------------------------------------------------- 写入


def createRoom(
    loginID: str,
    familyID: int,
    familyCode: str,
    roomName: str,
    templateID: int,
) -> dict:
    """开桌（04 §6 #25）。

    校验顺序：成员 → 模板可见/启用 → 族就绪 → 规则可解析 → 生成邀请码 → 一个事务写房。
    任何一步失败都在写库之前抛出，`mj_room` 不会留下半条记录。
    """
    _assertMember(loginID, familyID, requireEnabled=True)

    name = (roomName or "").strip()
    if not name:
        raise _err("BAD_REQUEST", "房间名称不能为空")
    # 模板 → 快照只在这里生成一次；之后改模板不影响本房间（03 §1、§11）
    templateRow, _config, snapshot = ruleService.openableTemplate(loginID, familyID, templateID)

    ruleFamilyCode = _text(templateRow, "ruleFamilyCode")

    recID = 0
    codeExhausted = True
    roomCode = ""
    for _ in range(ROOM_CODE_RETRY):
        code = _randomRoomCode()
        if mysqlCommon.query_mj_room_by_code(code):
            continue  # 邀请码已占用，换一个
        codeExhausted = False
        roomCode = code
        now = misc.getTime()
        dataSet = {
            "roomCode": code,
            "familyID": familyID,
            "roomName": name[:64],
            "hostLoginID": loginID,
            "templateID": int(templateRow.get("recID") or 0),
            "ruleFamilyCode": ruleFamilyCode,
            "ruleSnapshot": snapshot,
            "roomStatus": ROOM_OPEN,
            "createdYMDHMS": now,
            "regID": loginID,
            "regYMDHMS": now,
            "delFlag": "0",
        }
        try:
            with mysqlCommon.transaction():
                recID = mysqlCommon.insert_mj_room(mysqlCommon.MJ_ROOM_TABLE, dataSet)
                if recID <= 0:
                    # 唯一键冲突或写失败：回滚本次插入，换码重试
                    raise _err("DB_WRITE_FAILED", "开桌失败，请重试", 500)
            break
        except RoomServiceError:
            recID = 0
            continue

    if recID <= 0:
        if codeExhausted:
            raise _err("ROOM_CODE_EXHAUSTED", "邀请码生成失败，请重试", 500)
        raise _err("DB_WRITE_FAILED", "开桌失败，请重试", 500)

    logger.info("开桌 login=%s family=%s code=%s room=%s", loginID, familyCode, roomCode, recID)
    return roomOut(mysqlCommon.query_mj_room_by_id(recID), familyCode=familyCode)


def closeRoom(
    loginID: str,
    roomID: int,
    playerCount: int = 0,
    spectatorCount: int = 0,
) -> dict:
    """关房（04 §6 #29）：房主或房间所属家庭的管理员；重复关闭幂等。

    凭码进房的外家庭成员没有 `memberRole`，只能以房主身份关自己的房。
    """
    row = _loadRoom(roomID)
    context, isMember = _roomFamilyContext(loginID, int(row.get("familyID") or 0))
    isHost = _text(row, "hostLoginID") == loginID
    isAdmin = isMember and context.get("memberRole") in (
        familyService.ROLE_OWNER,
        familyService.ROLE_ADMIN,
    )
    if not isHost and not isAdmin:
        raise _err("FORBIDDEN", "只有房主可以关闭房间", 403)

    affected = mysqlCommon.update_mj_room_close(roomID, loginID)
    if affected < 0:
        raise _err("DB_WRITE_FAILED", "数据保存失败，请重试", 500)
    logger.info("关房 login=%s room=%s", loginID, roomID)
    return roomOut(
        _loadRoom(roomID),
        playerCount=playerCount,
        spectatorCount=spectatorCount,
        familyCode=context.get("familyCode", ""),
    )


# ---------------------------------------------------------------- 实时层握手


def roomMetaByCode(loginID: str, roomCode: str) -> dict:
    """WS 握手用的房间元信息（04 §9.1）：家庭可用 → 状态 → 规则快照。

    S9：邀请码即入场凭证，非本家庭登录用户也能握手进桌；家庭停用仍整房拒绝。
    失败抛 RoomServiceError，由 `main/ws.py` 映射成 4003/4004 关闭码。
    """
    code = (roomCode or "").strip().upper()
    if len(code) != 6 or not code.isdigit() or code[0] == "0":
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)
    row = mysqlCommon.query_mj_room_by_code(code)
    if not row:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)
    context, isMember = _roomFamilyContext(
        loginID, int(row.get("familyID") or 0), requireEnabled=True
    )
    if _text(row, "roomStatus") == ROOM_CLOSED:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)

    family = context.get("family") or {}
    return {
        # 非本家庭成员凭码进桌要房主确认（S10）；房主自己总是直接进
        "is_member": bool(isMember) or _text(row, "hostLoginID") == loginID,
        "room_id": int(row.get("recID") or 0),
        "room_code": _text(row, "roomCode"),
        "room_name": _text(row, "roomName"),
        "host_login_id": _text(row, "hostLoginID"),
        "family_id": int(row.get("familyID") or 0),
        "family_code": _text(family, "familyCode"),
        "family_name": _text(family, "familyName"),
        "rule_family_code": _text(row, "ruleFamilyCode"),
        "rule_name": _text(row, "templateName") or "自定义规则",
        "rule_snapshot": row.get("ruleSnapshot") if isinstance(row.get("ruleSnapshot"), dict) else {},
        "rule_config": ruleConfigOf(row),
    }
