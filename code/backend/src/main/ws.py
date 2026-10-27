"""WebSocket 端点：鉴权 → 绑定连接 → 分发到 RoomActor。"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from config.localSettings import settings
from main.deps import user_from_token
from common.loggingCommon import get_logger
from db.base import SessionLocal
from db.models import Room, RuleTemplate
from realtime import persist
from realtime.manager import room_manager
from schemas.rule import RuleConfig
from schemas.ws import make_message, parse_envelope

router = APIRouter()
logger = get_logger("mahjong.ws")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "", code: str = "") -> None:
    await websocket.accept()
    room_code = (code or "").strip().upper()

    user = None
    room_meta = None
    with SessionLocal() as session:
        user = user_from_token(session, token) if token else None
        if user is not None and room_code:
            room = session.scalar(select(Room).where(Room.code == room_code))
            if room is not None and room.status != "closed":
                template = (
                    session.get(RuleTemplate, room.rule_template_id)
                    if room.rule_template_id
                    else None
                )
                room_meta = {
                    "room_id": room.id,
                    "name": room.name,
                    "host_id": room.host_id,
                    "rule_name": template.name if template else "自定义规则",
                    "rule_config": RuleConfig.model_validate(room.rule_snapshot or {}),
                }

    if user is None:
        await websocket.send_json(
            make_message("error", {"code": "UNAUTHORIZED", "message": "登录已失效，请重新登录"})
        )
        await websocket.close(code=4001)
        return
    if room_meta is None:
        await websocket.send_json(
            make_message("error", {"code": "ROOM_NOT_FOUND", "message": "房间不存在或已关闭"})
        )
        await websocket.close(code=4004)
        return

    actor = room_manager.get_or_create(
        code=room_code,
        room_id=room_meta["room_id"],
        name=room_meta["name"],
        host_id=room_meta["host_id"],
        rule=room_meta["rule_config"],
        rule_name=room_meta["rule_name"],
    )

    async with actor.lock:
        slot = actor.assign(user)
        actor.attach(user.id, websocket)
    if slot is None:
        await actor.send_error(user.id, "ROOM_FULL", "四个座位都坐满了，你先观战吧")

    await actor.send(
        user.id,
        make_message(
            "room.welcome",
            {
                "room": {
                    "code": actor.code,
                    "name": actor.name,
                    "host_id": actor.host_id,
                    "rule_name": actor.rule_name,
                    "rule_brief": actor.rule.brief(),
                },
                "self_seat": slot.seat if slot else None,
                "chat": persist.load_messages(actor.room_id, 50),
            },
        ),
    )
    await actor.push_all()
    logger.info(
        "连接建立 room=%s user=%s seat=%s", room_code, user.id, slot.seat if slot else "观战"
    )

    try:
        while True:
            raw = await websocket.receive_json()
            envelope = parse_envelope(raw)
            if envelope is None:
                await actor.send_error(user.id, "BAD_MESSAGE", "消息格式不对")
                continue
            try:
                await actor.handle(user.id, {"type": envelope.type, "data": envelope.data})
            except Exception as error:  # noqa: BLE001 单条消息异常不能影响其他人
                logger.warning("处理消息失败 room=%s user=%s: %s", room_code, user.id, error)
                await actor.send_error(user.id, "INTERNAL", "服务端处理出错，请重试")
    except WebSocketDisconnect:
        logger.info("连接断开 room=%s user=%s", room_code, user.id)
    finally:
        async with actor.lock:
            actor.detach(user.id, websocket)
        await actor.push_all()
        if not actor.conns and settings.seat_reserve_seconds >= 0:
            logger.info("房间无在线连接 room=%s（座位保留中）", room_code)
