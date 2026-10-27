"""杂项公共函数：时间与 JSON。

本文件只放与业务无关、上下游都能用的零碎工具，不放麻将规则、数据库访问与 HTTP 代码。

时间口径（02 §2.1 / 01 §8.3）：库内时间列一律 `VARCHAR(16)`，格式 `YYYYMMDDHHMMSS`，
时区固定 Asia/Shanghai；对外输出再转 ISO 8601（+08:00）。业务代码禁止自行 `datetime.now()`
拼库时间，统一走这里的 `getTime()`。
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

def _buildTimezone():
    """东八区：优先 tzdata，缺失时退化为固定 +08:00（不带夏令时，足够本项目）。"""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Shanghai")
    except Exception:
        return timezone(timedelta(hours=8))


_TZ = _buildTimezone()

_logger = logging.getLogger("mahjong.misc")

_DB_TIME_FORMAT = "%Y%m%d%H%M%S"

__all__ = [
    "addTime",
    "diffTime",
    "getHumanTimeStamp",
    "getTime",
    "isoToYmdhms",
    "jsonDumps",
    "jsonLoads",
    "nowDb",
    "stableColorOf",
    "ymdhmsToIso",
]


# ---------- 时间 ----------


def nowDb() -> datetime:
    """当前时间（Asia/Shanghai，带时区）。"""
    return datetime.now(_TZ)


def getTime() -> str:
    """库时间：YYYYMMDDHHMMSS（14 位，落 VARCHAR(16)）。"""
    return nowDb().strftime(_DB_TIME_FORMAT)


def getHumanTimeStamp() -> str:
    """人类可读时间：YYYY-MM-DD HH:MM:SS（日志与生成器文件头用）。"""
    return nowDb().strftime("%Y-%m-%d %H:%M:%S")


def parseYmdhms(ymdhms: str) -> datetime | None:
    """解析 14 位库时间，失败返回 None（调用方自行兜底）。"""
    text = (ymdhms or "").strip()
    if len(text) < 14:
        return None
    try:
        return datetime.strptime(text[:14], _DB_TIME_FORMAT).replace(tzinfo=_TZ)
    except ValueError:
        return None


def ymdhmsToIso(ymdhms: str) -> str:
    """库时间 -> ISO 8601（带 +08:00）；非法输入原样返回，避免接口 500。"""
    moment = parseYmdhms(ymdhms)
    if moment is None:
        return ymdhms or ""
    return moment.isoformat(timespec="seconds")


def isoToYmdhms(isoText: str) -> str:
    """ISO 8601 -> 库时间；解析失败返回空串。"""
    text = (isoText or "").strip()
    if not text:
        return ""
    if len(text) == 14 and text.isdigit():
        return text
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_TZ)
    return moment.astimezone(_TZ).strftime(_DB_TIME_FORMAT)


def addTime(ymdhms: str, seconds: int) -> str:
    """库时间加减秒数，返回库时间；解析失败返回空串。"""
    moment = parseYmdhms(ymdhms)
    if moment is None:
        return ""
    return (moment + timedelta(seconds=int(seconds))).strftime(_DB_TIME_FORMAT)


def diffTime(beginYMDHMS: str, endYMDHMS: str) -> int:
    """两个库时间相差秒数（end - begin）；任一非法返回 0。"""
    begin = parseYmdhms(beginYMDHMS)
    end = parseYmdhms(endYMDHMS)
    if begin is None or end is None:
        return 0
    return int((end - begin).total_seconds())


# ---------- JSON ----------


def jsonDumps(value: Any) -> str:
    """写库用的紧凑 JSON：保留中文，不转义，不带多余空格。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# 玩家标识色板（04 §7 players[].color）。库里不存颜色，按 loginID 稳定散列：
# 同一用户在任何接口、任何进程里都得到同一个颜色，重启不变。
_PLAYER_COLOR_LIST = (
    "#C9A063",
    "#6B9BD1",
    "#D1836B",
    "#7FA78A",
    "#B088C4",
    "#D1B36B",
    "#6BB7B0",
    "#A88A6B",
)


def stableColorOf(key: Any) -> str:
    """按标识取稳定颜色（同一 key 恒返回同一色，key 为空时给默认色）。"""
    text = str(key or "").strip()
    if not text:
        return _PLAYER_COLOR_LIST[0]
    checksum = 0
    for char in text:
        checksum = (checksum * 31 + ord(char)) & 0xFFFFFFFF
    return _PLAYER_COLOR_LIST[checksum % len(_PLAYER_COLOR_LIST)]


def jsonLoads(text: Any, default: Any = None) -> Any:
    """容错解析：失败返回 default（dict 默认 {}、list 默认 []），并记 warning。

    02 §5 要求读取侧「解析失败不使整个接口 500」，故此处不抛异常。
    """
    if default is None:
        default = {}
    if text is None or text == "":
        return default
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        _logger.warning("JSON 解析失败，已按默认值返回：%.80s", text)
        return default
