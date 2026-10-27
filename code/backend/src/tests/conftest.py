"""测试公用的手牌解析与引擎构造工具。

手牌写法：123m 456p 789s 11z
- m 万 / p 筒 / s 条 / z 字（1z=东 … 7z=白）
"""

import os
import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SRC_DIR))

# 测试库独立，绝不动开发/生产数据。必须在导入 config.localSettings 之前设置。
# 跑测试产生的库同样属于附属数据，统一落在 code/backend/data/test/。
_TEST_DATA_DIR = _SRC_DIR.parent / "data" / "test"
_TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = _TEST_DATA_DIR / "test_mahjong.db"
for suffix in ("", "-wal", "-shm"):
    stale = Path(str(TEST_DB) + suffix)
    if stale.exists():
        stale.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ.setdefault("SECRET_KEY", "test-only-secret")
os.environ.setdefault("ADMIN_INIT_PASSWORD", "test-admin-pass")

from game.engine import GameEngine, SeatState  # noqa: E402
from schemas.rule import RuleConfig  # noqa: E402

_SUITS = {"m": 0, "p": 1, "s": 2}


def parse_hand(text: str) -> list[int]:
    tiles: list[int] = []
    pending: list[int] = []
    for char in text:
        if char.isdigit():
            pending.append(int(char))
            continue
        if char in " ,":
            pending.clear()
            continue
        if char in _SUITS:
            base = _SUITS[char]
            tiles.extend(base * 9 + number - 1 for number in pending)
            pending.clear()
        elif char == "z":
            tiles.extend(27 + number - 1 for number in pending)
            pending.clear()
        else:
            raise ValueError(f"看不懂的牌面写法：{char}")
    return tiles


def make_engine(rule: RuleConfig | None = None, dealer_seat: int = 0) -> GameEngine:
    seats = [
        SeatState(seat=i, user_id=i + 1, display_name=f"玩家{i}", color="#C9A063")
        for i in range(4)
    ]
    return GameEngine(rule or RuleConfig(), seats, round_no=1, dealer_seat=dealer_seat)


@pytest.fixture
def hand():
    return parse_hand


@pytest.fixture
def engine_factory():
    return make_engine
