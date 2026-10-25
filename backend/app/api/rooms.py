"""房间：创建、按邀请码查询、关闭、历史消息。"""

import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user
from app.db.models import Room, RuleTemplate, User
from app.realtime import persist
from app.realtime.manager import room_manager
from app.schemas.room import ChatMessageOut, RoomCreateRequest, RoomJoinCheck, RoomOut
from app.schemas.rule import RuleConfig

router = APIRouter(prefix="/rooms", tags=["rooms"])

_CODE_ALPHABET = string.digits + "ABCDEFGHJKLMNPQRSTUVWXYZ"  # 去掉易混的 O/I


def _new_code(session: Session) -> str:
    for _ in range(50):
        code = "".join(random.SystemRandom().choice(_CODE_ALPHABET) for _ in range(6))
        if session.scalar(select(Room).where(Room.code == code)) is None:
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="邀请码生成失败，请重试"
    )


def _room_out(session: Session, room: Room) -> RoomOut:
    host = session.get(User, room.host_id)
    template = (
        session.get(RuleTemplate, room.rule_template_id) if room.rule_template_id else None
    )
    actor = room_manager.get(room.code)
    player_count = sum(1 for slot in actor.slots if slot) if actor else 0
    return RoomOut(
        id=room.id,
        code=room.code,
        name=room.name,
        host_id=room.host_id,
        host_name=host.display_name if host else "未知",
        rule_template_id=room.rule_template_id,
        rule_name=template.name if template else "自定义规则",
        status=room.status,
        created_at=room.created_at.isoformat(),
        player_count=player_count,
    )


@router.post("", response_model=RoomOut)
def create_room(
    payload: RoomCreateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RoomOut:
    template = session.get(RuleTemplate, payload.rule_template_id)
    if template is None or not template.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则模板不存在")
    if not template.is_preset and template.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="这套规则不是你的")
    config = RuleConfig.model_validate(template.config or {})
    room = Room(
        code=_new_code(session),
        name=payload.name.strip(),
        host_id=user.id,
        rule_template_id=template.id,
        # 开房时把规则快照下来，之后改模板不影响这局
        rule_snapshot=config.model_dump(),
        status="open",
    )
    session.add(room)
    session.commit()
    return _room_out(session, room)


@router.get("", response_model=list[RoomOut])
def my_rooms(
    user: User = Depends(get_current_user), session: Session = Depends(db_session)
) -> list[RoomOut]:
    rows = session.scalars(
        select(Room)
        .where(Room.host_id == user.id, Room.status != "closed")
        .order_by(Room.id.desc())
        .limit(20)
    ).all()
    return [_room_out(session, row) for row in rows]


@router.get("/code/{code}", response_model=RoomJoinCheck)
def join_check(
    code: str,
    _: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RoomJoinCheck:
    room = session.scalar(select(Room).where(Room.code == code.strip().upper()))
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有这个房间，检查一下邀请码")
    if room.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这个房间已经关闭了")
    host = session.get(User, room.host_id)
    template = (
        session.get(RuleTemplate, room.rule_template_id) if room.rule_template_id else None
    )
    actor = room_manager.get(room.code)
    count = sum(1 for slot in actor.slots if slot) if actor else 0
    return RoomJoinCheck(
        code=room.code,
        name=room.name,
        host_name=host.display_name if host else "未知",
        rule_name=template.name if template else "自定义规则",
        status=room.status,
        player_count=count,
    )


@router.post("/{room_id}/close", response_model=RoomOut)
def close_room(
    room_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> RoomOut:
    room = session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
    if room.host_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有房主可以关闭房间")
    room.status = "closed"
    from app.db.models import utcnow

    room.closed_at = utcnow()
    session.commit()
    room_manager.remove(room.code)
    return _room_out(session, room)


@router.get("/{room_id}/messages", response_model=list[ChatMessageOut])
def room_messages(
    room_id: int,
    limit: int = 50,
    _: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> list[ChatMessageOut]:
    room = session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
    rows = persist.load_messages(room_id, max(1, min(limit, 200)))
    names = {
        user.id: user.display_name
        for user in session.scalars(select(User)).all()
    }
    return [
        ChatMessageOut(
            id=row["id"],
            room_id=row["room_id"],
            user_id=row["user_id"],
            user_name=names.get(row["user_id"], "系统") if row["user_id"] else "系统",
            kind=row["kind"],
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
