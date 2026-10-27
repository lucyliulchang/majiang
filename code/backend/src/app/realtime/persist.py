"""实时层的落库操作。

原则：每局结束立即落库，把"进程重启丢牌局"的损失限制在当前这一局。
"""

from datetime import datetime, timezone

from app.db.base import SessionLocal
from app.db.models import Game, GamePlayer, GameRound, RoomMessage


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def open_game(room_id: int, rule_snapshot: dict, seats: list[tuple[int, int]]) -> int:
    """创建一场牌并写入座位，返回 game_id。seats 为 (seat, user_id)。"""
    with SessionLocal() as session:
        game = Game(room_id=room_id, rule_snapshot=rule_snapshot, status="playing")
        session.add(game)
        session.flush()
        for seat, user_id in seats:
            session.add(GamePlayer(game_id=game.id, seat=seat, user_id=user_id, total_score=0))
        session.commit()
        return game.id


def save_round(game_id: int, settled, seat_users: dict[int, int]) -> None:
    with SessionLocal() as session:
        session.add(
            GameRound(
                game_id=game_id,
                round_no=settled.round_no,
                dealer_seat=settled.dealer_seat,
                winner_seat=settled.winner_seat,
                win_type=settled.win_type,
                winning_tile=settled.winning_tile,
                pattern_id=settled.pattern_id,
                fan_items=settled.fan_items,
                fan_total=settled.fan_total,
                score_delta=settled.score_delta,
            )
        )
        players = (
            session.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()
        )
        by_seat = {player.seat: player for player in players}
        for seat, delta in enumerate(settled.score_delta):
            player = by_seat.get(seat)
            if player is None:
                continue
            player.total_score += delta
            expected = seat_users.get(seat)
            if expected is not None and player.user_id != expected:
                player.user_id = expected
        session.commit()


def close_game(game_id: int) -> None:
    with SessionLocal() as session:
        game = session.get(Game, game_id)
        if game is None:
            return
        game.status = "finished"
        game.ended_at = utcnow()
        session.commit()


def save_message(room_id: int, user_id: int | None, kind: str, content: str) -> dict:
    with SessionLocal() as session:
        message = RoomMessage(
            room_id=room_id, user_id=user_id, kind=kind, content=content, created_at=utcnow()
        )
        session.add(message)
        session.commit()
        return {
            "id": message.id,
            "room_id": room_id,
            "user_id": user_id,
            "kind": kind,
            "content": content,
            "created_at": message.created_at.isoformat(),
        }


def load_messages(room_id: int, limit: int = 50) -> list[dict]:
    with SessionLocal() as session:
        rows = (
            session.query(RoomMessage)
            .filter(RoomMessage.room_id == room_id)
            .order_by(RoomMessage.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [
            {
                "id": row.id,
                "room_id": row.room_id,
                "user_id": row.user_id,
                "kind": row.kind,
                "content": row.content,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
