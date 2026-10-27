"""战绩域服务：场次列表、场次明细、个人统计（04 §7）。

性能口径（S5 验收）：
  - 列表：2 条 SQL（场次 + 参与者批量），与场次数无关，彻底消除逐场次查询的 N+1；
  - 详情：3 条 SQL（场次+房间+模板 / 参与者 / 逐局）；
  - 统计：2 条 SQL（汇总 + 胡牌局数）。
分页统一 `recID < before_id ORDER BY recID DESC LIMIT ?`，默认 30、最大 100。
"""

from __future__ import annotations

from common import miscCommon as misc
from common import mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from game.tiles import tile_name
from processor import familyService

logger = get_logger("mahjong.history")

DEFAULT_GAME_LIMIT = 30
MAX_GAME_LIMIT = 100

FAMILY_ADMIN_ROLES = (familyService.ROLE_OWNER, familyService.ROLE_ADMIN)


class HistoryServiceError(BizError):
    """战绩域业务异常。"""


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _iso(ymdhms: str) -> str:
    return misc.ymdhmsToIso(ymdhms)


def _limitOf(limit: int) -> int:
    value = int(limit or 0)
    if value <= 0:
        return DEFAULT_GAME_LIMIT
    return min(value, MAX_GAME_LIMIT)


def playerOut(row: dict) -> dict:
    """场次参与者（04 §7 players[]）：昵称优先结算快照，颜色按 loginID 稳定散列。"""
    playerLoginID = _text(row, "loginID")
    return {
        "seat": int(row.get("seatNo") or 0),
        "login_id": playerLoginID,
        "display_name": _text(row, "displayName") or playerLoginID or "已删除成员",
        "color": misc.stableColorOf(playerLoginID),
        "total_score": int(row.get("totalScore") or 0),
    }


def gameOut(row: dict, players: list[dict]) -> dict:
    """04 §7 games[] 的一项。"""
    return {
        "id": int(row.get("recID") or 0),
        "room_name": _text(row, "roomName") or "已删除的房间",
        "rule_name": _text(row, "ruleName") or "自定义规则",
        "status": _text(row, "gameStatus") or "PLAYING",
        "started_at": _iso(_text(row, "startedYMDHMS")),
        "ended_at": _iso(_text(row, "endedYMDHMS")) or None,
        "my_score": int(row.get("myScore") or 0),
        "players": players,
    }


def listGames(
    loginID: str,
    familyID: int,
    limit: int = DEFAULT_GAME_LIMIT,
    beforeID: int = 0,
) -> list[dict]:
    """我的场次（04 §7 #31）：只列本家庭内自己参与过的场次。"""
    familyService.assertMemberOfFamilyID(loginID, familyID)
    limit = _limitOf(limit)
    games = mysqlCommon.query_mj_game_list(familyID, loginID, limit=limit, beforeID=beforeID)
    if not games:
        return []

    rows = mysqlCommon.query_mj_game_player_list_by_games(
        [row.get("recID") for row in games]
    )
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(int(row.get("gameID") or 0), []).append(playerOut(row))

    return [gameOut(row, grouped.get(int(row.get("recID") or 0), [])) for row in games]


def gameDetail(loginID: str, gameID: int, operatorIsSystemAdmin: bool = False) -> dict:
    """场次明细（04 §7 #32）：参与者 / 家庭管理员 / 系统管理员可读。"""
    detail = mysqlCommon.query_mj_game_detail(gameID)
    game = detail.get("game") or {}
    if not game:
        raise HistoryServiceError("GAME_NOT_FOUND", "场次不存在", 404)

    familyID = int(game.get("familyID") or 0)
    context = familyService.assertMemberOfFamilyID(loginID, familyID)
    players = detail.get("players") or []
    isPlayer = any(_text(row, "loginID") == loginID for row in players)
    isFamilyAdmin = context.get("memberRole") in FAMILY_ADMIN_ROLES
    if not (isPlayer or isFamilyAdmin or operatorIsSystemAdmin):
        raise HistoryServiceError("FORBIDDEN", "这场牌你没参加", 403)

    snapshot = game.get("ruleSnapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    ruleSnapshot = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else snapshot

    rounds = []
    for row in detail.get("rounds") or []:
        winnerRaw = _text(row, "winnerSeat")
        tileRaw = _text(row, "winningTile")
        rounds.append(
            {
                "round_no": int(row.get("roundNo") or 0),
                "dealer_seat": int(row.get("dealerSeat") or 0),
                "round_wind": int(row.get("roundWind") or 0),
                "winner_seat": int(winnerRaw) if winnerRaw != "" else None,
                "win_type": _text(row, "winType") or "none",
                "winning_tile_name": tile_name(int(tileRaw)) if tileRaw != "" else None,
                "pattern_id": _text(row, "patternID") or None,
                "fan_items": row.get("fanItemsJson")
                if isinstance(row.get("fanItemsJson"), list)
                else [],
                "fan_raw": int(row.get("fanRaw") or 0),
                "fan_total": int(row.get("fanTotal") or 0),
                "score_delta": row.get("scoreDeltaJson")
                if isinstance(row.get("scoreDeltaJson"), list)
                else [],
            }
        )

    return {
        "id": int(game.get("recID") or 0),
        "family_code": _text(context, "familyCode"),
        "room_name": _text(game, "roomName") or "已删除的房间",
        "rule_name": _text(game, "ruleName") or "自定义规则",
        "rule_snapshot": ruleSnapshot,
        "status": _text(game, "gameStatus") or "PLAYING",
        "started_at": _iso(_text(game, "startedYMDHMS")),
        "ended_at": _iso(_text(game, "endedYMDHMS")) or None,
        "players": [playerOut(row) for row in players],
        "rounds": rounds,
    }


def myStats(loginID: str, familyID: int) -> dict:
    """个人统计（04 §7 #33）。"""
    familyService.assertMemberOfFamilyID(loginID, familyID)
    raw = mysqlCommon.query_mj_game_stats(loginID, familyID)
    return {
        "total_score": int(raw.get("totalScore") or 0),
        "games_played": int(raw.get("gamesPlayed") or 0),
        "rounds_won": int(raw.get("roundsWon") or 0),
        "best_game": int(raw.get("bestGame") or 0),
        "worst_game": int(raw.get("worstGame") or 0),
    }
