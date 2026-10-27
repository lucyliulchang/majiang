"""牌编码与牌墙。

编码：tile = suit*9 + rank-1
- 0-8   万（一万..九万）
- 9-17  筒
- 18-26 条
- 27-30 东南西北
- 31-33 中发白
共 34 种，每种 4 张，合计 136 张。
"""

import random

TILE_KINDS = 34
COPIES_PER_TILE = 4
WALL_SIZE = TILE_KINDS * COPIES_PER_TILE  # 136

# 牌张集合（03 §2.2 capability.tile_set）：136 = 万筒条 + 字牌；108 = 万筒条各 36，无字牌
TILE_SET_136 = "136"
TILE_SET_108 = "108"
TILE_SET_KINDS: dict[str, int] = {TILE_SET_136: 34, TILE_SET_108: 27}


SUIT_WAN = 0
SUIT_TONG = 1
SUIT_TIAO = 2
SUIT_HONOR = 3

_NUM_CN = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]
_SUIT_CN = ["万", "筒", "条"]
_HONOR_CN = ["东", "南", "西", "北", "中", "发", "白"]

WIND_TILES = (27, 28, 29, 30)  # 东南西北
DRAGON_TILES = (31, 32, 33)  # 中发白


def is_suit(tile: int) -> bool:
    """是否为数牌（万/筒/条）。"""
    return 0 <= tile < 27


def is_honor(tile: int) -> bool:
    return 27 <= tile < 34


def suit_of(tile: int) -> int:
    if is_suit(tile):
        return tile // 9
    return SUIT_HONOR


def rank_of(tile: int) -> int:
    """数牌返回 0-8（对应一到九），字牌返回 0-6。"""
    if is_suit(tile):
        return tile % 9
    return tile - 27


def tile_name(tile: int) -> str:
    if not 0 <= tile < TILE_KINDS:
        return "?"
    if is_suit(tile):
        return f"{_NUM_CN[rank_of(tile)]}{_SUIT_CN[suit_of(tile)]}"
    return _HONOR_CN[tile - 27]


def tiles_name(tiles: list[int]) -> str:
    return " ".join(tile_name(t) for t in tiles)


def empty_counts() -> list[int]:
    return [0] * TILE_KINDS


def tile_kinds_of(tile_set_code: str = TILE_SET_136) -> int:
    """牌张集合对应的牌种数；未知集合抛 ValueError（注册表导入期自检用）。"""
    kinds = TILE_SET_KINDS.get(str(tile_set_code))
    if kinds is None:
        raise ValueError(f"未知的牌张集合「{tile_set_code}」，只支持 136 / 108")
    return kinds


def tile_set_of(tile_set_code: str = TILE_SET_136) -> tuple[int, ...]:
    """可用的牌编码集合（capability 自检用）。"""
    return tuple(range(tile_kinds_of(tile_set_code)))


def new_wall(rng: random.Random | None = None, tile_set_code: str = TILE_SET_136) -> list[int]:
    """造一副牌墙并洗牌。默认 136 张、系统随机源，服务端权威。"""
    kinds = tile_kinds_of(tile_set_code)
    wall = [tile for tile in range(kinds) for _ in range(COPIES_PER_TILE)]
    (rng or random.SystemRandom()).shuffle(wall)
    return wall


def counts_from_tiles(tiles: list[int]) -> list[int]:
    counts = empty_counts()
    for tile in tiles:
        counts[tile] += 1
    return counts


def tiles_from_counts(counts: list[int]) -> list[int]:
    result: list[int] = []
    for tile, count in enumerate(counts):
        result.extend([tile] * count)
    return result


def sort_tiles(tiles: list[int]) -> list[int]:
    return sorted(tiles)
