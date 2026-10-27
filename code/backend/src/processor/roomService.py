"""房间域服务：开桌 / 房间列表 / 入房校验 / 关房 / 聊天记录（04 §6）。

职责边界（01 §2）：
  - 路由只解析参数、调本模块、套响应模型；
  - 本模块负责成员校验（按房间自身的 familyID，不信查询参数）、模板可见性与族就绪校验、
    邀请码生成、事务与错误码；
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


def joinCheckOut(row: dict, playerCount: int = 0, viewerCounts: list[int] | None = None) -> dict:
    """04 §6 的 room_join_check 结构。

    `viewer_counts` 来自内存房态（`RoomActor.spectator_counts`）；`available=false`
    表示 4 座已满且 40 个观战位全满，前端据此禁用「进入观战」。
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
    """房间详情：以房间自身 familyID 校验成员关系（04 §6 #27）。"""
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
    """按邀请码入房校验（04 §6 #28）：格式 → 存在 → 成员 → 状态。"""
    code = (roomCode or "").strip()
    if len(code) != 6 or not code.isdigit() or code[0] == "0":
        raise _err("INVITE_CODE_FORMAT", "邀请码必须是 6 位数字")
    row = mysqlCommon.query_mj_room_by_code(code)
    if not row:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)
    _assertMember(loginID, int(row.get("familyID") or 0))
    if _text(row, "roomStatus") == ROOM_CLOSED:
        raise _err("ROOM_CLOSED", "房间已经关闭了")
    return joinCheckOut(row, playerCount=playerCount, viewerCounts=viewerCounts)


def listMessages(loginID: str, roomID: int, limit: int = 50) -> list[dict]:
    """最近聊天（04 §6 #30）：必带 LIMIT，返回按时间正序。"""
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
    """关房（04 §6 #29）：房主或家庭管理员；重复关闭幂等。"""
    row = _loadRoom(roomID)
    context = _assertMember(loginID, int(row.get("familyID") or 0))
    isHost = _text(row, "hostLoginID") == loginID
    isAdmin = context.get("memberRole") in (
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
    """WS 握手用的房间元信息（04 §9.1）：成员 → 状态 → 规则快照。

    失败抛 RoomServiceError，由 `main/ws.py` 映射成 4003/4004 关闭码。
    """
    code = (roomCode or "").strip().upper()
    if len(code) != 6 or not code.isdigit() or code[0] == "0":
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)
    row = mysqlCommon.query_mj_room_by_code(code)
    if not row:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)
    context = _assertMember(loginID, int(row.get("familyID") or 0), requireEnabled=True)
    if _text(row, "roomStatus") == ROOM_CLOSED:
        raise _err("ROOM_NOT_FOUND", "房间不存在或已关闭", 404)

    family = context.get("family") or {}
    return {
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
