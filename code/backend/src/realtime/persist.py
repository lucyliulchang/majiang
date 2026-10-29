"""实时层的落库操作（S5：全部走 mysqlCommon + 事务）。

原则（01 §7.4、§9）：
  1. 每局结束立即落库，把"进程重启丢牌局"的损失限制在当前这一局；
  2. 一个业务动作一个事务：开局（game + players）、结算（round + totalScore）必须原子；
  3. 这些函数是**同步阻塞**的，只能在 `run_in_threadpool` 里调用（见 realtime/room.py），
     绝不能在协程里直接触库。
"""

from __future__ import annotations

from common import miscCommon as misc
from common import mysqlCommon
from common.bizCommon import BizError
from common.loggingCommon import get_logger
from processor.roomService import messageOut

logger = get_logger("mahjong.persist")

GAME_PLAYING = "PLAYING"
GAME_FINISHED = "FINISHED"


class PersistError(BizError):
    """落库失败（不阻断对局，由调用方记录日志并提示）。"""


def _writeFailed(action: str) -> PersistError:
    return PersistError("DB_WRITE_FAILED", f"数据保存失败（{action}），请重试", 500)


def open_game(
    roomID: int,
    familyID: int,
    ruleFamilyCode: str,
    ruleSnapshot: dict,
    seats: list[tuple[int, str, str]],
    seatDraw: dict | None = None,
) -> int:
    """创建一场牌并写入座位，返回 game_id。

    `seats` 为 `(seatNo, loginID, displayName)`；game 与 4 条 player 在同一事务内，
    任何一条失败整体回滚，不会出现「有场次没座位」的半场数据。

    `ruleSnapshot` 必须是**开桌时**写进 `mj_room` 的那份（03 §11：开局以开桌快照为准），
    `seatDraw` 为每场首局的抽座与掷骰记录（02 `mj_game.seatDrawJson`）。
    """
    now = misc.getTime()
    dataSet = {
        "familyID": familyID,
        "roomID": roomID,
        "ruleFamilyCode": ruleFamilyCode,
        "ruleSnapshot": ruleSnapshot,
        "seatDrawJson": seatDraw or None,
        "gameStatus": GAME_PLAYING,
        "startedYMDHMS": now,
        "regYMDHMS": now,
        "delFlag": "0",
    }
    with mysqlCommon.transaction():
        gameID = mysqlCommon.insert_mj_game(mysqlCommon.MJ_GAME_TABLE, dataSet)
        if gameID <= 0:
            raise _writeFailed("开局")
        for seat, loginID, displayName in seats:
            inserted = mysqlCommon.insert_mj_game_player(
                mysqlCommon.MJ_GAME_PLAYER_TABLE,
                {
                    "gameSeatKey": f"{gameID}_{seat}",
                    "gameID": gameID,
                    "familyID": familyID,
                    "seatNo": seat,
                    "loginID": loginID,
                    "displayName": (displayName or "")[:40],
                    "totalScore": 0,
                    "regID": loginID,
                    "regYMDHMS": now,
                    "delFlag": "0",
                },
            )
            if inserted <= 0:
                raise _writeFailed("开局座位")
    logger.info("开局落库 room=%s game=%s players=%d", roomID, gameID, len(seats))
    return gameID


def save_round(gameID: int, familyID: int, settled) -> None:
    """一局结算落库：`mj_game_round` 与 `mj_game_player.totalScore` 同事务。

    totalScore 用 `UPDATE ... SET totalScore = totalScore + ?` 做自增，避免并发下
    「读旧值再写回」丢分；任一语句失败则整局回滚（不会出现「有局无分」或「有分无局」）。
    """
    roundNo = int(getattr(settled, "round_no", 1) or 1)
    # 局风看局序（第 1 局东…第 4 局北），与谁是庄家无关（03 §3.4）
    roundWind = getattr(settled, "round_wind", None)
    if roundWind is None:
        roundWind = max(0, roundNo - 1)
    dataSet = {
        "gameID": gameID,
        "familyID": familyID,
        "roundNo": roundNo,
        "dealerSeat": int(getattr(settled, "dealer_seat", 0) or 0),
        "roundWind": int(roundWind),
        "winnerSeat": getattr(settled, "winner_seat", None),
        "winType": getattr(settled, "win_type", "none") or "none",
        "winningTile": getattr(settled, "winning_tile", None),
        "patternID": getattr(settled, "pattern_id", None),
        "fanItemsJson": getattr(settled, "fan_items", []) or [],
        "fanRaw": int(getattr(settled, "fan_raw", 0) or getattr(settled, "fan_total", 0) or 0),
        "fanTotal": int(getattr(settled, "fan_total", 0) or 0),
        "scoreDeltaJson": getattr(settled, "score_delta", []) or [],
        # 付款方分配（S7：柏氏包牌独付、四川血战逐家赔付）；无分配时留空
        "payerJson": list(getattr(settled, "payer_allocation", []) or []) or None,
        "finishedYMDHMS": misc.getTime(),
    }
    scoreDelta = list(getattr(settled, "score_delta", []) or [])
    with mysqlCommon.transaction():
        recID = mysqlCommon.insert_mj_game_round_settlement(dataSet)
        if recID <= 0:
            raise _writeFailed("结算")
        for seat, delta in enumerate(scoreDelta):
            delta = int(delta or 0)
            if delta == 0:
                continue
            affected = mysqlCommon.update_mj_game_player_score(gameID, seat, delta)
            if affected <= 0:
                raise _writeFailed("结算计分")
    logger.info("结算落库 game=%s round=%s delta=%s", gameID, roundNo, scoreDelta)


def close_game(gameID: int) -> None:
    """结束一场：FINISHED + endedYMDHMS。不存在时静默（重复调用幂等）。"""
    if not gameID:
        return
    affected = mysqlCommon.update_mj_game_status(gameID, GAME_FINISHED)
    if affected < 0:
        raise _writeFailed("结束场次")


def save_message(
    roomID: int, familyID: int, loginID: str | None, kind: str, content: str
) -> dict:
    """写一条聊天/系统播报，返回 04 §9.4 的 chat.message 结构。"""
    now = misc.getTime()
    recID = mysqlCommon.insert_mj_room_message(
        mysqlCommon.MJ_ROOM_MESSAGE_TABLE,
        {
            "roomID": roomID,
            "familyID": familyID,
            "loginID": loginID or None,
            "messageKind": kind or "chat",
            "content": (content or "")[:500],
            "createdYMDHMS": now,
            "regID": loginID or "system",
            "regYMDHMS": now,
            "delFlag": "0",
        },
    )
    if recID <= 0:
        raise _writeFailed("聊天")
    row = {
        "recID": recID,
        "roomID": roomID,
        "loginID": loginID or "",
        "userName": "",
        "messageKind": kind,
        "content": content,
        "createdYMDHMS": now,
    }
    return messageOut(row)


def load_messages(roomID: int, limit: int = 50) -> list[dict]:
    """最近聊天（按时间正序）；查询必带 LIMIT。"""
    rows = mysqlCommon.query_mj_room_message_list(roomID, limit=limit)
    rows.reverse()
    return [messageOut(row) for row in rows]
