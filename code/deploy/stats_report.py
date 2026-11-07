#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""牌局战绩统计（只读）：胡牌牌型排行 + 玩家赢分排行，结果写 CSV。

数据来源（只读，不写库、不依赖后端进程）：
    mj_game_round   逐局结算：winnerSeat / winType / patternID / fanTotal /
                    fanItemsJson / scoreDeltaJson / finishedYMDHMS
    mj_game_player  每场座位：gameID + seatNo → loginID / displayName / totalScore

统计口径：
    1. 只算「已结算」的局（mj_game_round 有行且 delFlag=0）；winnerSeat 为 NULL 的荒庄
       不计入牌型统计，但计入玩家参与局数。
    2. 牌型 = patternID（standard / seven_pairs / thirteen_unrelated / thirteen_orphans /
       long_seven_pairs），按「平均番数」从高到低排序，同番按次数。
    3. 玩家分数取 scoreDeltaJson（每局四家真实分差，已含包牌/一炮多响的分配），
       不用 fanTotal 折算；净分与 mj_game_player.totalScore 在摘要里交叉校验。

用法（服务器上，连接信息默认从 .env 读，不写死口令）：
    python3 stats_report.py                              # 全量统计
    python3 stats_report.py --days 30                    # 最近 30 天
    python3 stats_report.py --since 2026-11-01 --until 2026-11-30
    python3 stats_report.py --family-id 10 --out-dir /tmp/mjstats
    python3 stats_report.py --with-fan-items             # 额外输出番种明细排行
    python3 stats_report.py --self-test                  # 离线自检聚合逻辑（不连库）

输出（文件名带统计时间戳，UTF-8 BOM，Excel 直接打开不乱码）：
    pattern_stats_<时间戳>.csv    牌型排行（按平均番数从高到低）
    player_stats_<时间戳>.csv     玩家排行（默认按净赢分从高到低）
    fan_item_stats_<时间戳>.csv   --with-fan-items 时的番种明细排行
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# 牌型 ID → 中文名（与 game/families/*/patterns.py 的 id/name 保持一致）
PATTERN_NAMES = {
    "standard": "标准胡",
    "seven_pairs": "七小对",
    "long_seven_pairs": "龙七对",
    "thirteen_unrelated": "13不靠",
    "thirteen_orphans": "十三幺",
}

WIN_TYPE_NAMES = {"self_draw": "自摸", "discard": "点炮", "rob_kong": "抢杠"}

# 环境变量回退顺序：写库 → 读库 → 内置默认（与 config/mysqlSettings.py 对齐）
ENV_KEYS = {
    "host": ("MYSQL_WRITE_HOST", "MYSQL_READ_HOST"),
    "port": ("MYSQL_WRITE_PORT", "MYSQL_READ_PORT"),
    "db": ("MYSQL_WRITE_DB", "MYSQL_READ_DB"),
    "user": ("MYSQL_WRITE_USER", "MYSQL_READ_USER"),
    "password": ("MYSQL_WRITE_PASSWD", "MYSQL_READ_PASSWD"),
}
DEFAULT_DB = {"host": "127.0.0.1", "port": 3306, "db": "mahjong_data", "user": "mjapp", "password": ""}


# ---------------------------------------------------------------- 配置与连接


def loadEnvFile(envPath: Path) -> None:
    """把 .env 灌进 os.environ（不覆盖已有环境变量）；文件不存在时静默跳过。"""
    if not envPath or not envPath.is_file():
        return
    try:
        text = envPath.read_text(encoding="utf-8")
    except OSError:
        return
    for rawLine in text.splitlines():
        line = rawLine.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def findEnvFile(cliPath: str, scriptDir: Path) -> Path | None:
    """按「显式指定 → 当前目录 → 生产部署路径 → 仓库内路径」的顺序找 .env。"""
    candidates = []
    if cliPath:
        candidates.append(Path(cliPath))
    candidates.extend(
        [
            Path.cwd() / ".env",
            Path("/data/majiang/src/.env"),
            scriptDir.parent / "backend" / "src" / ".env",
            scriptDir / ".env",
        ]
    )
    for path in candidates:
        if path and path.is_file():
            return path
    return None


def _envFirst(keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return default


def dbConfigOf(args) -> dict:
    """命令行优先，其次 .env / 环境变量，最后内置默认。"""
    config = {}
    for field, keys in ENV_KEYS.items():
        default = str(DEFAULT_DB[field])
        cliValue = getattr(args, field, None)
        config[field] = (str(cliValue).strip() if cliValue not in (None, "") else "") or _envFirst(keys, default)
    config["port"] = int(config["port"] or 3306)
    return config


def connectDb(config: dict):
    """惰性导入 pymysql：连不上数据库时本脚本仍可 --self-test / 读代码。"""
    try:
        import pymysql
    except ImportError:
        print("[错误] 缺少 pymysql，请先安装：pip install pymysql", file=sys.stderr)
        raise SystemExit(2)
    return pymysql.connect(
        host=config["host"],
        port=int(config["port"]),
        user=config["user"],
        password=config["password"],
        database=config["db"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
        read_timeout=60,
    )


# ---------------------------------------------------------------- 时间口径


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def timeBound(value: str, isEnd: bool) -> str:
    """把 2026-11-01 / 2026-11-01 12:00 之类归一成库里 14 位 YYYYMMDDHHMMSS。"""
    raw = _digits(value)
    if len(raw) == 8:
        return raw + ("235959" if isEnd else "000000")
    if len(raw) == 10:
        return raw + ("59" if isEnd else "00")
    if len(raw) == 12:
        return raw + ("59" if isEnd else "00")
    if len(raw) == 14:
        return raw
    raise ValueError(f"无法识别的时间：{value}（支持 YYYY-MM-DD / YYYY-MM-DD HH:MM）")


def timeRangeOf(args) -> tuple[str, str]:
    """返回 (since, until)，都用 14 位字符串；未指定时为全量。"""
    since, until = "", ""
    if getattr(args, "days", 0):
        start = datetime.now() - timedelta(days=int(args.days))
        since = start.strftime("%Y%m%d") + "000000"
        until = datetime.now().strftime("%Y%m%d") + "235959"
    if args.since:
        since = timeBound(args.since, False)
    if args.until:
        until = timeBound(args.until, True)
    return since, until


def displayTime(ymdhms: str) -> str:
    """20261107115436 → 2026-11-07 11:54:36；长度不对就原样返回。"""
    text = str(ymdhms or "")
    if len(text) == 14 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}"
    return text


# ---------------------------------------------------------------- 取数


def fetchRounds(conn, since: str, until: str, familyID: int, excludeRooms: list[int]) -> list[dict]:
    """拉逐局结算明细（家庭麻将量级：几千行，Python 侧聚合比写复杂 SQL 更好维护）。"""
    sql = [
        "SELECT r.recID, r.gameID, r.familyID, r.roundNo, r.winnerSeat, r.winType,",
        "       r.patternID, r.fanRaw, r.fanTotal, r.fanItemsJson, r.scoreDeltaJson,",
        "       r.finishedYMDHMS, g.roomID, g.ruleFamilyCode",
        "  FROM mj_game_round r",
        "  LEFT JOIN mj_game g ON g.recID = r.gameID",
        " WHERE (r.delFlag = '0' OR r.delFlag IS NULL)",
    ]
    params: list = []
    if since:
        sql.append("   AND r.finishedYMDHMS >= %s")
        params.append(since)
    if until:
        sql.append("   AND r.finishedYMDHMS <= %s")
        params.append(until)
    if familyID:
        sql.append("   AND r.familyID = %s")
        params.append(int(familyID))
    if excludeRooms:
        sql.append("   AND (g.roomID IS NULL OR g.roomID NOT IN (%s))" % ",".join(["%s"] * len(excludeRooms)))
        params.extend(int(room) for room in excludeRooms)
    sql.append(" ORDER BY r.recID ASC")

    with conn.cursor() as cursor:
        cursor.execute("\n".join(sql), tuple(params))
        rows = list(cursor.fetchall() or [])

    result = []
    for row in rows:
        result.append(
            {
                "recID": int(row.get("recID") or 0),
                "gameID": int(row.get("gameID") or 0),
                "familyID": int(row.get("familyID") or 0),
                "roomID": int(row.get("roomID") or 0),
                "roundNo": int(row.get("roundNo") or 0),
                "winnerSeat": None if row.get("winnerSeat") is None else int(row.get("winnerSeat")),
                "winType": str(row.get("winType") or "none"),
                "patternID": str(row.get("patternID") or ""),
                "fanRaw": int(row.get("fanRaw") or 0),
                "fanTotal": int(row.get("fanTotal") or 0),
                "fanItems": parseJsonList(row.get("fanItemsJson")),
                "scoreDelta": parseJsonList(row.get("scoreDeltaJson")),
                "finishedYMDHMS": str(row.get("finishedYMDHMS") or ""),
                "ruleFamilyCode": str(row.get("ruleFamilyCode") or ""),
            }
        )
    return result


def fetchPlayers(conn, gameIDs: list[int]) -> dict[int, dict[int, dict]]:
    """{gameID: {seatNo: {loginID, displayName, totalScore}}}，按 500 个 gameID 一批。"""
    result: dict[int, dict[int, dict]] = defaultdict(dict)
    ids = sorted({int(gid) for gid in gameIDs if int(gid or 0) > 0})
    for offset in range(0, len(ids), 500):
        batch = ids[offset : offset + 500]
        sql = (
            "SELECT gameID, seatNo, loginID, displayName, totalScore FROM mj_game_player "
            " WHERE (delFlag = '0' OR delFlag IS NULL) AND gameID IN (%s)"
            % ",".join(["%s"] * len(batch))
        )
        with conn.cursor() as cursor:
            cursor.execute(sql, tuple(batch))
            for row in cursor.fetchall() or []:
                gameID = int(row.get("gameID") or 0)
                seat = int(row.get("seatNo") or 0)
                result[gameID][seat] = {
                    "loginID": str(row.get("loginID") or ""),
                    "displayName": str(row.get("displayName") or "") or str(row.get("loginID") or ""),
                    "gameTotalScore": int(row.get("totalScore") or 0),
                }
    return result


def parseJsonList(value) -> list:
    """MySQL JSON 列在 pymysql 下可能已是对象，也可能是字符串；统一返回 list。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            import json

            parsed = json.loads(text)
        except (ValueError, TypeError):
            return []
        return list(parsed) if isinstance(parsed, list) else []
    return []


# ---------------------------------------------------------------- 聚合：牌型


def newPatternStat(patternID: str) -> dict:
    return {
        "patternID": patternID,
        "hands": 0,
        "fanTotal": 0,
        "fanRaw": 0,
        "maxFan": 0,
        "minFan": None,
        "capped": 0,
        "winPoints": 0,
        "selfDraw": 0,
        "discard": 0,
        "robKong": 0,
        "fanItemCount": 0,
        "fanCounter": defaultdict(lambda: {"name": "", "count": 0, "fan": 0}),
    }


def buildPatternStats(rounds: list[dict]) -> dict:
    """按 patternID 汇总；返回 {stats: [...], totalWins, drawRounds}。"""
    stats: dict[str, dict] = {}
    totalWins = 0
    drawRounds = 0
    for row in rounds:
        if row["winnerSeat"] is None:
            drawRounds += 1
            continue
        patternID = row["patternID"] or "unknown"
        stat = stats.setdefault(patternID, newPatternStat(patternID))
        stat["hands"] += 1
        stat["fanTotal"] += row["fanTotal"]
        stat["fanRaw"] += row["fanRaw"]
        stat["maxFan"] = max(stat["maxFan"], row["fanTotal"])
        stat["minFan"] = row["fanTotal"] if stat["minFan"] is None else min(stat["minFan"], row["fanTotal"])
        if row["fanTotal"] < row["fanRaw"]:
            stat["capped"] += 1
        deltas = row["scoreDelta"]
        winnerSeat = row["winnerSeat"]
        if 0 <= winnerSeat < len(deltas):
            try:
                stat["winPoints"] += int(deltas[winnerSeat] or 0)
            except (TypeError, ValueError):
                pass
        if row["winType"] == "self_draw":
            stat["selfDraw"] += 1
        elif row["winType"] == "rob_kong":
            stat["robKong"] += 1
        else:
            stat["discard"] += 1
        items = row["fanItems"]
        stat["fanItemCount"] += len(items)
        for item in items:
            if not isinstance(item, dict):
                continue
            fanID = str(item.get("id") or "")
            if not fanID:
                continue
            count = int(item.get("count") or 1)
            fan = int(item.get("fan") or 0)
            entry = stat["fanCounter"][fanID]
            entry["name"] = str(item.get("name") or fanID)
            entry["count"] += count
            entry["fan"] += fan * count
        totalWins += 1

    ordered = sorted(
        stats.values(),
        key=lambda stat: (-(stat["fanTotal"] / stat["hands"]), -stat["hands"], stat["patternID"]),
    )
    return {"stats": ordered, "totalWins": totalWins, "drawRounds": drawRounds}


def topFanItems(stat: dict, topN: int = 3) -> str:
    """牌型行里的「高频番种」列：按出现次数取前 N，形如「混龙×12；258赢×9」。"""
    items = sorted(stat["fanCounter"].items(), key=lambda pair: (-pair[1]["count"], -pair[1]["fan"]))
    parts = []
    for _, entry in items[:topN]:
        parts.append(f"{entry['name']}×{entry['count']}")
    return "；".join(parts)


# ---------------------------------------------------------------- 聚合：玩家


def newPlayerStat(loginID: str, displayName: str) -> dict:
    return {
        "loginID": loginID,
        "displayName": displayName,
        "games": set(),
        "rounds": 0,
        "roundsWon": 0,
        "selfDraw": 0,
        "netScore": 0,
        "winPoints": 0,
        "lossPoints": 0,
        "winRounds": 0,
        "lossRounds": 0,
        "bestRound": 0,
        "worstRound": 0,
        "fanTotal": 0,
        "maxFan": 0,
        "firstTime": "",
        "lastTime": "",
    }


def buildPlayerStats(rounds: list[dict], playersByGame: dict) -> list[dict]:
    """按 loginID 汇总：净分 / 赢分 / 输分 / 胡牌 / 胜率 / 单局极值 / 番数。"""
    stats: dict[str, dict] = {}
    for row in rounds:
        seats = playersByGame.get(row["gameID"]) or {}
        deltas = row["scoreDelta"]
        finished = row["finishedYMDHMS"]
        for seat in range(len(deltas)):
            player = seats.get(seat)
            if not player or not player["loginID"]:
                continue
            loginID = player["loginID"]
            stat = stats.get(loginID)
            if stat is None:
                stat = newPlayerStat(loginID, player["displayName"])
                stats[loginID] = stat
            try:
                delta = int(deltas[seat] or 0)
            except (TypeError, ValueError):
                delta = 0
            stat["games"].add(row["gameID"])
            stat["rounds"] += 1
            stat["netScore"] += delta
            if delta > 0:
                stat["winPoints"] += delta
                stat["winRounds"] += 1
            elif delta < 0:
                stat["lossPoints"] += delta
                stat["lossRounds"] += 1
            stat["bestRound"] = max(stat["bestRound"], delta)
            stat["worstRound"] = min(stat["worstRound"], delta)
            if finished:
                if not stat["firstTime"] or finished < stat["firstTime"]:
                    stat["firstTime"] = finished
                if finished >= stat["lastTime"]:
                    stat["lastTime"] = finished
                    stat["displayName"] = player["displayName"] or stat["displayName"]
            if row["winnerSeat"] == seat:
                stat["roundsWon"] += 1
                stat["fanTotal"] += row["fanTotal"]
                stat["maxFan"] = max(stat["maxFan"], row["fanTotal"])
                if row["winType"] == "self_draw":
                    stat["selfDraw"] += 1
    return list(stats.values())


SORT_KEYS = {
    "net": lambda stat: (-stat["netScore"], stat["loginID"]),
    "win": lambda stat: (-stat["winPoints"], stat["loginID"]),
    "avg": lambda stat: (-(stat["netScore"] / stat["rounds"] if stat["rounds"] else 0), stat["loginID"]),
    "rate": lambda stat: (
        -(stat["roundsWon"] / stat["rounds"] if stat["rounds"] else 0),
        -stat["netScore"],
        stat["loginID"],
    ),
    "best": lambda stat: (-stat["bestRound"], -stat["netScore"], stat["loginID"]),
}


def sortPlayers(rows: list[dict], sortKey: str) -> list[dict]:
    return sorted(rows, key=SORT_KEYS.get(sortKey, SORT_KEYS["net"]))


# ---------------------------------------------------------------- 聚合：番种


def buildFanItemStats(rounds: list[dict]) -> list[dict]:
    """番种明细排行：出现次数 / 累计番 / 平均番 / 涉及牌型。"""
    stats: dict[str, dict] = {}
    for row in rounds:
        if row["winnerSeat"] is None:
            continue
        for item in row["fanItems"]:
            if not isinstance(item, dict):
                continue
            fanID = str(item.get("id") or "")
            if not fanID:
                continue
            entry = stats.setdefault(
                fanID,
                {"fanID": fanID, "name": str(item.get("name") or fanID), "count": 0, "fan": 0, "patterns": set()},
            )
            count = int(item.get("count") or 1)
            entry["name"] = str(item.get("name") or entry["name"])
            entry["count"] += count
            entry["fan"] += int(item.get("fan") or 0) * count
            entry["patterns"].add(row["patternID"] or "unknown")
    return sorted(stats.values(), key=lambda entry: (-entry["count"], -entry["fan"], entry["fanID"]))


# ---------------------------------------------------------------- CSV 输出


def _ratio(part: int, total: int) -> str:
    return f"{(part * 100.0 / total):.2f}" if total else "0.00"


def _avg(total: float, count: int) -> str:
    return f"{(total / count):.2f}" if count else "0.00"


def writeCsv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def writePatternCsv(path: Path, built: dict) -> int:
    header = [
        "排名",
        "牌型ID",
        "牌型名称",
        "胡牌次数",
        "胡牌占比%",
        "平均番数",
        "最高番数",
        "最低番数",
        "封顶次数",
        "平均赢分",
        "总赢分",
        "自摸",
        "点炮",
        "抢杠",
        "平均番种数",
        "高频番种",
    ]
    rows = []
    totalWins = built["totalWins"] or 0
    for index, stat in enumerate(built["stats"], start=1):
        rows.append(
            [
                index,
                stat["patternID"],
                PATTERN_NAMES.get(stat["patternID"], stat["patternID"]),
                stat["hands"],
                _ratio(stat["hands"], totalWins),
                _avg(stat["fanTotal"], stat["hands"]),
                stat["maxFan"],
                stat["minFan"] if stat["minFan"] is not None else 0,
                stat["capped"],
                _avg(stat["winPoints"], stat["hands"]),
                stat["winPoints"],
                stat["selfDraw"],
                stat["discard"],
                stat["robKong"],
                _avg(stat["fanItemCount"], stat["hands"]),
                topFanItems(stat),
            ]
        )
    writeCsv(path, header, rows)
    return len(rows)


def writePlayerCsv(path: Path, players: list[dict], minRounds: int) -> int:
    header = [
        "排名",
        "玩家ID",
        "昵称",
        "参与场次",
        "参与局数",
        "胡牌次数",
        "胡牌率%",
        "自摸次数",
        "自摸占胡牌%",
        "净分",
        "赢分合计",
        "输分合计",
        "场均净分",
        "赢局平均分",
        "单局最高分",
        "单局最低分",
        "胡牌平均番数",
        "最高番数",
        "场均番数",
        "首次对局",
        "最近对局",
    ]
    rows = []
    index = 0
    for stat in players:
        if minRounds and stat["rounds"] < minRounds:
            continue
        index += 1
        rows.append(
            [
                index,
                stat["loginID"],
                stat["displayName"],
                len(stat["games"]),
                stat["rounds"],
                stat["roundsWon"],
                _ratio(stat["roundsWon"], stat["rounds"]),
                stat["selfDraw"],
                _ratio(stat["selfDraw"], stat["roundsWon"]),
                stat["netScore"],
                stat["winPoints"],
                stat["lossPoints"],
                _avg(stat["netScore"], stat["rounds"]),
                _avg(stat["winPoints"], stat["winRounds"]),
                stat["bestRound"],
                stat["worstRound"],
                _avg(stat["fanTotal"], stat["roundsWon"]),
                stat["maxFan"],
                _avg(stat["fanTotal"], stat["rounds"]),
                displayTime(stat["firstTime"]),
                displayTime(stat["lastTime"]),
            ]
        )
    writeCsv(path, header, rows)
    return len(rows)


def writeFanItemCsv(path: Path, items: list[dict]) -> int:
    header = ["排名", "番种ID", "番种名称", "出现次数", "累计番数", "平均番数", "涉及牌型数"]
    rows = []
    for index, item in enumerate(items, start=1):
        rows.append(
            [
                index,
                item["fanID"],
                item["name"],
                item["count"],
                item["fan"],
                _avg(item["fan"], item["count"]),
                len(item["patterns"]),
            ]
        )
    writeCsv(path, header, rows)
    return len(rows)


# ---------------------------------------------------------------- 主流程


def runReport(args) -> int:
    scriptDir = Path(__file__).resolve().parent
    since, until = timeRangeOf(args)
    envFile = findEnvFile(args.env_file, scriptDir)
    if envFile:
        loadEnvFile(envFile)
        print(f"[信息] 配置文件：{envFile}")
    else:
        print("[信息] 未找到 .env，改用环境变量/命令行参数（口令请用 --password 或环境变量传入）")
    config = dbConfigOf(args)
    print(
        f"[信息] 数据库：{config['host']}:{config['port']}/{config['db']} user={config['user']}"
        f"；时间范围：{since or '不限'} ~ {until or '不限'}"
        + (f"；家庭：{args.family_id}" if args.family_id else "")
    )

    excludeRooms = []
    if args.exclude_rooms:
        excludeRooms = [int(item) for item in str(args.exclude_rooms).replace("，", ",").split(",") if item.strip()]

    conn = connectDb(config)
    try:
        rounds = fetchRounds(conn, since, until, args.family_id, excludeRooms)
        if not rounds:
            print("[提示] 该范围内没有已结算的牌局，未生成 CSV。")
            return 0
        playersByGame = fetchPlayers(conn, [row["gameID"] for row in rounds])
    finally:
        conn.close()

    built = buildPatternStats(rounds)
    players = sortPlayers(buildPlayerStats(rounds, playersByGame), args.sort_player)
    fanItems = buildFanItemStats(rounds) if args.with_fan_items else []

    outDir = Path(args.out_dir).expanduser().resolve()
    outDir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    patternPath = outDir / f"pattern_stats_{stamp}.csv"
    playerPath = outDir / f"player_stats_{stamp}.csv"

    patternCount = writePatternCsv(patternPath, built)
    playerCount = writePlayerCsv(playerPath, players, args.min_rounds)
    fanPath = None
    fanCount = 0
    if args.with_fan_items:
        fanPath = outDir / f"fan_item_stats_{stamp}.csv"
        fanCount = writeFanItemCsv(fanPath, fanItems)

    # 摘要：牌型榜前 5、玩家榜前 10、净分交叉校验
    print("\n== 牌型排行（按平均番数从高到低）==")
    for index, stat in enumerate(built["stats"][:5], start=1):
        name = PATTERN_NAMES.get(stat["patternID"], stat["patternID"])
        print(
            f"{index}. {name:<6} {stat['hands']:>4} 次  平均 {_avg(stat['fanTotal'], stat['hands'])} 番"
            f"  最高 {stat['maxFan']} 番  平均赢 {_avg(stat['winPoints'], stat['hands'])} 分"
        )
    print("\n== 玩家排行（按净分从高到低）==")
    ranked = [stat for stat in players if not args.min_rounds or stat["rounds"] >= args.min_rounds]
    for index, stat in enumerate(ranked[:10], start=1):
        print(
            f"{index}. {stat['displayName']:<8} 净分 {stat['netScore']:>5}"
            f"  赢 {stat['winPoints']:>5}  输 {stat['lossPoints']:>6}"
            f"  场次 {len(stat['games']):>2}  局数 {stat['rounds']:>3}  胡 {stat['roundsWon']:>3}"
            f"  胜率 {_ratio(stat['roundsWon'], stat['rounds'])}%"
        )

    netSum = sum(stat["netScore"] for stat in players)
    seatTotalSum = sum(
        player.get("gameTotalScore", 0) for seats in playersByGame.values() for player in seats.values()
    )
    print("\n== 校验 ==")
    print(f"局数 {len(rounds)}（其中荒庄 {built['drawRounds']}，胡牌 {built['totalWins']}）")
    print(f"玩家净分合计 {netSum}（应为 0）；mj_game_player.totalScore 合计 {seatTotalSum}")

    print("\n== 输出文件 ==")
    print(f"牌型统计（{patternCount} 行）：{patternPath}")
    print(f"玩家统计（{playerCount} 行）：{playerPath}")
    if fanPath is not None:
        print(f"番种统计（{fanCount} 行）：{fanPath}")
    return 0


# ---------------------------------------------------------------- 离线自检


def selfTest() -> int:
    """内置 3 局样本，校验聚合与排序（不需要数据库）。"""
    rounds = [
        {  # game 1 round 1：座位 0 自摸 3 番
            "recID": 1,
            "gameID": 1,
            "familyID": 1,
            "roomID": 1,
            "roundNo": 1,
            "winnerSeat": 0,
            "winType": "self_draw",
            "patternID": "standard",
            "fanRaw": 3,
            "fanTotal": 3,
            "fanItems": [
                {"id": "ping_hu", "name": "平胡", "fan": 1, "count": 1},
                {"id": "que_men", "name": "缺门", "fan": 1, "count": 1},
                {"id": "jiang_pai", "name": "将牌", "fan": 1, "count": 1},
            ],
            "scoreDelta": [6, -2, -2, -2],
            "finishedYMDHMS": "20261101120000",
            "ruleFamilyCode": "baishi",
        },
        {  # game 1 round 2：座位 1 点炮被座位 3 胡，混龙 10 番
            "recID": 2,
            "gameID": 1,
            "familyID": 1,
            "roomID": 1,
            "roundNo": 2,
            "winnerSeat": 3,
            "winType": "discard",
            "patternID": "standard",
            "fanRaw": 14,
            "fanTotal": 14,
            "fanItems": [
                {"id": "hun_long", "name": "混龙", "fan": 10, "count": 1},
                {"id": "du_ying", "name": "独赢", "fan": 1, "count": 1},
            ],
            "scoreDelta": [-14, -28, -14, 56],
            "finishedYMDHMS": "20261101121000",
            "ruleFamilyCode": "baishi",
        },
        {  # game 2 round 1：座位 2 七小对自摸 21 番
            "recID": 3,
            "gameID": 2,
            "familyID": 1,
            "roomID": 2,
            "roundNo": 1,
            "winnerSeat": 2,
            "winType": "self_draw",
            "patternID": "seven_pairs",
            "fanRaw": 21,
            "fanTotal": 21,
            "fanItems": [
                {"id": "qi_xiao_dui", "name": "七小对", "fan": 20, "count": 1},
                {"id": "men_qian", "name": "门清", "fan": 1, "count": 1},
            ],
            "scoreDelta": [-7, -7, 21, -7],
            "finishedYMDHMS": "20261102120000",
            "ruleFamilyCode": "baishi",
        },
    ]
    playersByGame = {
        1: {
            0: {"loginID": "p0", "displayName": "甲", "gameTotalScore": -8},
            1: {"loginID": "p1", "displayName": "乙", "gameTotalScore": -30},
            2: {"loginID": "p2", "displayName": "丙", "gameTotalScore": -16},
            3: {"loginID": "p3", "displayName": "丁", "gameTotalScore": 54},
        },
        2: {
            0: {"loginID": "p0", "displayName": "甲", "gameTotalScore": -7},
            1: {"loginID": "p1", "displayName": "乙", "gameTotalScore": -7},
            2: {"loginID": "p2", "displayName": "丙", "gameTotalScore": 21},
            3: {"loginID": "p3", "displayName": "丁", "gameTotalScore": -7},
        },
    }
    built = buildPatternStats(rounds)
    players = buildPlayerStats(rounds, playersByGame)

    failures = []
    if built["totalWins"] != 3 or built["drawRounds"] != 0:
        failures.append(f"胡牌/荒庄计数错误：{built['totalWins']}/{built['drawRounds']}")
    if [stat["patternID"] for stat in built["stats"]] != ["seven_pairs", "standard"]:
        failures.append(f"牌型应按平均番数降序：{[s['patternID'] for s in built['stats']]}")
    standard = next(stat for stat in built["stats"] if stat["patternID"] == "standard")
    if standard["hands"] != 2 or round(standard["fanTotal"] / standard["hands"], 2) != 8.5:
        failures.append(f"标准胡聚合错误：{standard['hands']} 次 / {standard['fanTotal']} 番")
    if standard["winPoints"] != 62:
        failures.append(f"标准胡赢分应为 6+56=62，实际 {standard['winPoints']}")

    byID = {stat["loginID"]: stat for stat in players}
    if byID["p3"]["netScore"] != 47:
        failures.append(f"p3 净分应为 -2+56-7=47，实际 {byID['p3']['netScore']}")
    if sum(stat["netScore"] for stat in players) != 0:
        failures.append("玩家净分合计不为 0")
    ranked = sortPlayers(players, "net")
    if ranked[0]["loginID"] != "p3":
        failures.append(f"净分第一应为 p3，实际 {ranked[0]['loginID']}")
    if byID["p1"]["rounds"] != 3 or byID["p1"]["roundsWon"] != 0:
        failures.append(f"p1 局数/胡牌错误：{byID['p1']['rounds']}/{byID['p1']['roundsWon']}")

    print("== 自检 ==")
    for stat in ranked:
        print(
            f"{stat['displayName']} 净分={stat['netScore']} 局数={stat['rounds']}"
            f" 胡={stat['roundsWon']} 赢分={stat['winPoints']} 输分={stat['lossPoints']}"
        )
    for stat in built["stats"]:
        print(f"{stat['patternID']} 次数={stat['hands']} 平均番={_avg(stat['fanTotal'], stat['hands'])}")
    if failures:
        print("[自检失败]")
        for item in failures:
            print("  - " + item)
        return 1
    print("[自检通过]")
    return 0


# ---------------------------------------------------------------- 入口


def parseArgs(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计已打完的牌局：胡牌牌型排行 + 玩家赢分排行（输出 CSV）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 stats_report.py --days 30 --with-fan-items\n"
            "  python3 stats_report.py --since 2026-11-01 --until 2026-11-30 --out-dir /tmp/mjstats\n"
            "  python3 stats_report.py --self-test\n"
        ),
    )
    parser.add_argument("--env-file", default="", help=".env 路径（默认自动查找 /data/majiang/src/.env 等）")
    parser.add_argument("--host", default="", help="MySQL 主机")
    parser.add_argument("--port", default="", help="MySQL 端口")
    parser.add_argument("--db", default="", help="库名")
    parser.add_argument("--user", default="", help="用户名")
    parser.add_argument("--password", default="", help="口令（建议用 .env 或环境变量，避免留在 shell 历史）")
    parser.add_argument("--family-id", type=int, default=0, help="只统计某个家庭（默认全部）")
    parser.add_argument("--since", default="", help="起始时间 YYYY-MM-DD[ HH:MM]（含）")
    parser.add_argument("--until", default="", help="截止时间 YYYY-MM-DD[ HH:MM]（含）")
    parser.add_argument("--days", type=int, default=0, help="统计最近 N 天（与 --since 同用时以 --since 为准）")
    parser.add_argument("--exclude-rooms", default="", help="排除房间号，逗号分隔（如冒烟房 126646,778107）")
    parser.add_argument("--out-dir", default="stats", help="CSV 输出目录（默认 ./stats）")
    parser.add_argument("--min-rounds", type=int, default=0, help="玩家最少参与局数（默认不过滤）")
    parser.add_argument(
        "--sort-player",
        default="net",
        choices=sorted(SORT_KEYS.keys()),
        help="玩家排序：net=净分(默认) / win=赢分合计 / avg=场均净分 / rate=胜率 / best=单局最高",
    )
    parser.add_argument("--with-fan-items", action="store_true", help="额外输出番种明细排行 CSV")
    parser.add_argument("--self-test", action="store_true", help="离线自检聚合逻辑，不连数据库")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parseArgs(list(sys.argv[1:] if argv is None else argv))
    if args.self_test:
        return selfTest()
    try:
        return runReport(args)
    except ValueError as error:
        print(f"[参数错误] {error}", file=sys.stderr)
        return 2
    except Exception as error:  # 连接失败等，给出可读提示而不是整段 traceback
        print(f"[执行失败] {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
