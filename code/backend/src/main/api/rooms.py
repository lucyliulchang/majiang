"""房间路由（04 §6，6 个端点）。

分层（01 §2）：解析参数 → 家庭上下文 → 调 roomService → 套响应模型。
房态实时值（在座人数 / 围观人数）来自内存 `room_manager`，不查库。
"""

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from main.deps import (
    CurrentUser,
    FamilyContext,
    current_active_family,
    current_user,
    familyContextOf,
)
from processor import roomService
from realtime.manager import room_manager
from schemas.room import ChatMessageOut, RoomCreateRequest, RoomJoinCheck, RoomOut

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _liveCounts(roomCode: str) -> tuple[int, int]:
    """(在座人数, 围观人数)：房态只在内存，无 actor 时都是 0。"""
    actor = room_manager.get(roomCode)
    if actor is None:
        return 0, 0
    return actor.player_count(), actor.spectator_count()


def _familyOf(
    user: CurrentUser, familyCode: str, fallback: FamilyContext
) -> FamilyContext:
    code = (familyCode or "").strip()
    if not code or code == fallback.family_code:
        return fallback
    return familyContextOf(user.login_id, code, requireEnabled=True)


@router.post("", response_model=RoomOut)
def create_room(
    payload: RoomCreateRequest,
    user: CurrentUser = Depends(current_user),
    context: FamilyContext = Depends(current_active_family),
) -> RoomOut:
    """开桌（04 §6 #25）：模板不存在/族未就绪时 `mj_room` 不落任何记录。"""
    family = _familyOf(user, payload.family_code, context)
    return RoomOut(
        **roomService.createRoom(
            user.login_id,
            family.family_id,
            family.family_code,
            payload.room_name,
            payload.template_id,
        )
    )


@router.get("", response_model=list[RoomOut])
def my_rooms(
    before_id: int = 0,
    context: FamilyContext = Depends(current_active_family),
) -> list[RoomOut]:
    """家庭房间列表：只列 OPEN，倒序，默认 20（04 §6 #26）。"""
    rows = roomService.listRooms(
        context.login_id, context.family_id, context.family_code, beforeID=before_id
    )
    result: list[RoomOut] = []
    for row in rows:
        players, spectators = _liveCounts(row["room_code"])
        result.append(RoomOut(**{**row, "player_count": players, "spectator_count": spectators}))
    return result


@router.get("/code/{room_code}", response_model=RoomJoinCheck)
def join_check(
    room_code: str,
    user: CurrentUser = Depends(current_user),
) -> RoomJoinCheck:
    """按邀请码入房校验（04 §6 #28）：含实时围观数（`spectate.available` 用于禁用进入）。"""
    actor = room_manager.get(room_code.strip().upper())
    players = actor.player_count() if actor is not None else 0
    viewers = actor.spectator_counts() if actor is not None else [0, 0, 0, 0]
    return RoomJoinCheck(**roomService.getRoomByCode(user.login_id, room_code, players, viewers))


@router.get("/{room_id}", response_model=RoomOut)
def get_room(
    room_id: int,
    user: CurrentUser = Depends(current_user),
) -> RoomOut:
    """房间详情（04 §6 #27）：以房间自身 familyID 校验成员关系。"""
    row = roomService.getRoom(user.login_id, room_id)
    players, spectators = _liveCounts(row["room_code"])
    return RoomOut(**{**row, "player_count": players, "spectator_count": spectators})


@router.post("/{room_id}/close", response_model=RoomOut)
async def close_room(
    room_id: int,
    user: CurrentUser = Depends(current_user),
) -> RoomOut:
    """关房（04 §6 #29）：房主/家庭管理员；通知观战者并销毁内存中的房间演员。"""
    row = await run_in_threadpool(roomService.closeRoom, user.login_id, room_id)
    actor = room_manager.get(row["room_code"])
    if actor is not None:
        # 先把"观战目标已失效"广播出去，再销毁演员
        await actor.close_spectate()
        room_manager.remove(row["room_code"])
    return RoomOut(**{**row, "player_count": 0, "spectator_count": 0})


@router.get("/{room_id}/messages", response_model=list[ChatMessageOut])
def room_messages(
    room_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(current_user),
) -> list[ChatMessageOut]:
    """最近聊天（04 §6 #30）：必带 LIMIT（默认 50，最大 200），按时间正序。"""
    rows = roomService.listMessages(user.login_id, room_id, limit)
    return [ChatMessageOut(**row) for row in rows]
