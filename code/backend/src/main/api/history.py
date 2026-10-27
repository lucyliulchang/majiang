"""战绩：场次列表、场次明细、个人统计。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from main.deps import db_session, get_current_user
from db.models import Game, GamePlayer, GameRound, Room, RuleTemplate, User
from game.tiles import tile_name

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/games")
def list_games(
    limit: int = 30,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> list[dict]:
    games = session.scalars(
        select(Game)
        .join(GamePlayer, GamePlayer.game_id == Game.id)
        .where(GamePlayer.user_id == user.id)
        .order_by(Game.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    result: list[dict] = []
    for game in games:
        players = session.scalars(
            select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.seat)
        ).all()
        users = {row.id: row for row in session.scalars(select(User)).all()}
        room = session.get(Room, game.room_id)
        mine = next((p.total_score for p in players if p.user_id == user.id), 0)
        result.append(
            {
                "id": game.id,
                "room_name": room.name if room else "已删除的房间",
                "status": game.status,
                "started_at": game.started_at.isoformat(),
                "ended_at": game.ended_at.isoformat() if game.ended_at else None,
                "my_score": mine,
                "players": [
                    {
                        "seat": player.seat,
                        "user_id": player.user_id,
                        "display_name": users[player.user_id].display_name
                        if player.user_id in users
                        else "已删除成员",
                        "color": users[player.user_id].color if player.user_id in users else "#6B7A72",
                        "total_score": player.total_score,
                    }
                    for player in players
                ],
            }
        )
    return result


@router.get("/games/{game_id}")
def game_detail(
    game_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(db_session),
) -> dict:
    game = session.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场次不存在")
    players = session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game_id).order_by(GamePlayer.seat)
    ).all()
    if user.id not in {player.user_id for player in players} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="这场牌你没参加")
    rounds = session.scalars(
        select(GameRound).where(GameRound.game_id == game_id).order_by(GameRound.round_no)
    ).all()
    users = {row.id: row for row in session.scalars(select(User)).all()}
    room = session.get(Room, game.room_id)
    template = (
        session.get(RuleTemplate, room.rule_template_id) if room and room.rule_template_id else None
    )
    return {
        "id": game.id,
        "room_name": room.name if room else "已删除的房间",
        "rule_name": template.name if template else "自定义规则",
        "rule_snapshot": game.rule_snapshot,
        "status": game.status,
        "started_at": game.started_at.isoformat(),
        "ended_at": game.ended_at.isoformat() if game.ended_at else None,
        "players": [
            {
                "seat": player.seat,
                "user_id": player.user_id,
                "display_name": users[player.user_id].display_name
                if player.user_id in users
                else "已删除成员",
                "color": users[player.user_id].color if player.user_id in users else "#6B7A72",
                "total_score": player.total_score,
            }
            for player in players
        ],
        "rounds": [
            {
                "round_no": item.round_no,
                "dealer_seat": item.dealer_seat,
                "winner_seat": item.winner_seat,
                "win_type": item.win_type,
                "winning_tile_name": tile_name(item.winning_tile)
                if item.winning_tile is not None
                else None,
                "pattern_id": item.pattern_id,
                "fan_items": item.fan_items,
                "fan_total": item.fan_total,
                "score_delta": item.score_delta,
            }
            for item in rounds
        ],
    }


@router.get("/stats")
def my_stats(
    user: User = Depends(get_current_user), session: Session = Depends(db_session)
) -> dict:
    players = session.scalars(select(GamePlayer).where(GamePlayer.user_id == user.id)).all()
    total = sum(player.total_score for player in players)
    best = max((player.total_score for player in players), default=0)
    worst = min((player.total_score for player in players), default=0)
    rounds_won = 0
    for player in players:
        rows = session.scalars(
            select(GameRound).where(
                GameRound.game_id == player.game_id,
                GameRound.winner_seat == player.seat,
            )
        ).all()
        rounds_won += len(rows)
    return {
        "total_score": total,
        "games_played": len(players),
        "best_game": best,
        "worst_game": worst,
        "rounds_won": rounds_won,
    }
