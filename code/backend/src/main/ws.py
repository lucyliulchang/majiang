"""WebSocket 端点：鉴权 → 绑定连接 → 分发到 RoomActor（04 §9.1）。

S5 口径：
  - 身份用 JWT 的 `sub`（loginID），回查 USER_BASIC 得昵称/启用状态，不再读 users 表；
  - 房间与规则走 `roomService.roomMetaByCode`（按房间 familyID 解析归属；邀请码即入场凭证，
    非本家庭登录用户也可握手，家庭停用仍拒绝）；
  - 本函数是协程：所有数据库访问都经 `run_in_threadpool`，不阻塞事件循环。
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from common import miscCommon as misc
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from config.localSettings import settings
from main.deps import current_user_from_token
from processor import roomService
from realtime import persist
from realtime.manager import room_manager
from realtime.snapshot import welcome_payload
from schemas.ws import make_message, parse_envelope

router = APIRouter()
logger = get_logger("mahjong.ws")

_CLOSE_UNAUTHORIZED = 4001
_CLOSE_BAD_VERSION = 4002
_CLOSE_FORBIDDEN = 4003
_CLOSE_ROOM_NOT_FOUND = 4004
_CLOSE_SPECTATE_FULL = 4005


async def _reject(websocket: WebSocket, code: str, message: str, closeCode: int) -> None:
    await websocket.send_json(make_message("error", {"code": code, "message": message}))
    await websocket.close(code=closeCode)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "", code: str = "") -> None:
    await websocket.accept()
    room_code = (code or "").strip().upper()

    user = await run_in_threadpool(current_user_from_token, token) if token else None
    if user is None:
        await _reject(websocket, "UNAUTHORIZED", "登录已失效，请重新登录", _CLOSE_UNAUTHORIZED)
        return
    if user.active_flag == "0":
        await _reject(websocket, "FORBIDDEN", "该账号已被停用", _CLOSE_FORBIDDEN)
        return

    try:
        meta = await run_in_threadpool(
            roomService.roomMetaByCode, user.login_id, room_code
        )
    except BizError as error:
        closeCode = (
            _CLOSE_FORBIDDEN
            if error.code in ("NOT_FAMILY_MEMBER", "FAMILY_DISABLED")
            else _CLOSE_ROOM_NOT_FOUND
        )
        await _reject(websocket, error.code, error.message, closeCode)
        return

    actor = room_manager.get_or_create(
        code=meta["room_code"],
        room_id=meta["room_id"],
        family_id=meta["family_id"],
        family_code=meta["family_code"],
        family_name=meta["family_name"],
        name=meta["room_name"],
        host_login_id=meta["host_login_id"],
        rule=meta["rule_config"],
        rule_name=meta["rule_name"],
        rule_snapshot=meta["rule_snapshot"],
    )

    display_name = user.display_name
    color = misc.stableColorOf(user.login_id)
    is_member = bool(meta.get("is_member"))
    slot = None
    join_pending = False
    async with actor.lock:
        if actor.needs_approval(user.login_id, is_member):
            # 非本家庭成员凭码进桌（S10）：先挂起，房主在牌桌上确认后才分配座位
            actor.add_pending(user.login_id, display_name, color, websocket)
            join_pending = True
            if actor.host_login_id in actor.conns:
                await actor.push_snapshot_to(actor.host_login_id)
        else:
            # 4 座满且 4×10 观战位满 → 4005 断开；满座但仍有名额只回 ROOM_FULL（非致命）
            if actor.slot_of_login(user.login_id) is None and actor.spectate_full():
                await _reject(
                    websocket,
                    "ROOM_SPECTATE_FULL",
                    "围观人数已满，暂时进不去",
                    _CLOSE_SPECTATE_FULL,
                )
                return
            slot = actor.assign(user.login_id, display_name, color)
            if slot is not None:
                await actor.drop_spectate(user.login_id)
            actor.attach(user.login_id, websocket)

    if join_pending:
        # 待确认：连接先留着，房主点「同意」后由 RoomActor 补 welcome + 快照
        await websocket.send_json(
            make_message(
                "room.join_pending",
                {
                    "room_code": actor.code,
                    "room_name": actor.name,
                    "family_name": actor.family_name,
                    "host_login_id": actor.host_login_id,
                    "message": "这是别人家的牌桌，已把进桌申请发给房主",
                },
            )
        )
        logger.info("进桌待房主确认 room=%s login=%s", room_code, user.login_id)
    else:
        if slot is None:
            await actor.send_error(
                user.login_id, "ROOM_FULL", "四个座位都坐满了，先选个家人观战吧"
            )
        chat = await run_in_threadpool(persist.load_messages, actor.room_id, 50)
        await actor.send(
            user.login_id,
            make_message("room.welcome", welcome_payload(actor, user.login_id, slot, chat)),
        )
        await actor.push_all()
        logger.info(
            "连接建立 room=%s login=%s seat=%s",
            room_code,
            user.login_id,
            slot.seat if slot else "观战",
        )

    try:
        while True:
            raw = await websocket.receive_json()
            envelope = parse_envelope(raw)
            if envelope is None:
                await websocket.send_json(
                    make_message("error", {"code": "BAD_MESSAGE", "message": "消息格式不对"})
                )
                continue
            # 还没获房主同意的访客：只回心跳，业务消息一律挡回（批准后本连接自动转正）
            if actor.is_pending_conn(user.login_id, websocket):
                if envelope.type == "ping":
                    await websocket.send_json(make_message("pong"))
                else:
                    await websocket.send_json(
                        make_message(
                            "error",
                            {"code": "JOIN_PENDING", "message": "等房主确认后就能进桌"},
                        )
                    )
                continue
            try:
                await actor.handle(
                    user.login_id, {"type": envelope.type, "data": envelope.data}
                )
                # 房主结束了牌局并关房：演员已销毁，本连接没有可推的房态了
                if actor.closed:
                    break
            except Exception as error:  # noqa: BLE001 单条消息异常不能影响其他人
                logger.warning(
                    "处理消息失败 room=%s login=%s: %s", room_code, user.login_id, error
                )
                await actor.send_error(user.login_id, "INTERNAL", "服务端处理出错，请重试")
    except WebSocketDisconnect:
        logger.info("连接断开 room=%s login=%s", room_code, user.login_id)
    finally:
        async with actor.lock:
            actor.detach(user.login_id, websocket)
        if not actor.closed:
            await actor.push_all()
        if not actor.conns and settings.seat_reserve_seconds >= 0:
            logger.info("房间无在线连接 room=%s（座位保留中）", room_code)
