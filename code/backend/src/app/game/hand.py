"""对局内部使用的牌型与手牌上下文。"""

from dataclasses import dataclass, field

from app.game.tiles import TILE_KINDS, is_honor, is_suit, rank_of, suit_of, tile_name

MeldKind = str  # "chow" | "pong" | "kong_exposed" | "kong_hidden" | "kong_added"

MELD_KIND_CN = {
    "chow": "吃",
    "pong": "碰",
    "kong_exposed": "明杠",
    "kong_hidden": "暗杠",
    "kong_added": "补杠",
}


@dataclass
class Meld:
    """一组已亮出的牌。tiles 按升序存放。"""

    kind: MeldKind
    tiles: list[int]
    from_seat: int | None = None

    @property
    def is_kong(self) -> bool:
        return self.kind.startswith("kong")

    @property
    def exposed(self) -> bool:
        """是否算作副露（暗杠不算暴露牌面内容，但也不属于门清）。"""
        return self.kind != "kong_hidden"

    def to_dict(self, reveal: bool = True) -> dict:
        return {
            "kind": self.kind,
            "kind_name": MELD_KIND_CN.get(self.kind, self.kind),
            "tiles": list(self.tiles) if reveal else [],
            "count": len(self.tiles),
            "from_seat": self.from_seat,
        }


@dataclass
class HandContext:
    """牌型判定所需的全部信息。counts 含刚到手的那张（win_tile 已计入）。"""

    counts: list[int]
    melds: list[Meld] = field(default_factory=list)
    win_tile: int | None = None
    is_self_draw: bool = False
    seat_wind: int = 0  # 0-3 对应东南西北
    round_wind: int = 0
    is_last_tile: bool = False  # 海底
    is_robbing_kong: bool = False
    is_after_kong: bool = False  # 杠上开花

    @property
    def total_tiles(self) -> int:
        return sum(self.counts) + sum(len(m.tiles) for m in self.melds)

    @property
    def has_exposed_meld(self) -> bool:
        return any(m.exposed for m in self.melds)

    @property
    def meld_tiles(self) -> list[int]:
        out: list[int] = []
        for meld in self.melds:
            out.extend(meld.tiles)
        return out

    def all_tiles(self) -> list[int]:
        out: list[int] = []
        for tile in range(TILE_KINDS):
            out.extend([tile] * self.counts[tile])
        out.extend(self.meld_tiles)
        return out

    def describe(self) -> str:
        parts = [tile_name(self.win_tile)] if self.win_tile is not None else []
        for meld in self.melds:
            parts.append(f"[{MELD_KIND_CN.get(meld.kind, meld.kind)}]")
        return " ".join(parts)


def suit_profile(counts: list[int], extra_tiles: list[int] | None = None) -> tuple[set[int], int]:
    """返回（出现过的花色集合, 字牌张数）。"""
    suits: set[int] = set()
    honors = 0
    for tile, count in enumerate(counts):
        if count <= 0:
            continue
        if is_honor(tile):
            honors += count
        else:
            suits.add(suit_of(tile))
    for tile in extra_tiles or []:
        if is_honor(tile):
            honors += 1
        else:
            suits.add(suit_of(tile))
    return suits, honors


def ranks_in_suit(counts: list[int], suit: int) -> list[int]:
    base = suit * 9
    return [rank_of(base + r) for r in range(9) if counts[base + r] > 0]


def numbered_kinds(counts: list[int], extra: list[int] | None = None) -> list[int]:
    kinds = [t for t in range(27) if counts[t] > 0]
    for tile in extra or []:
        if is_suit(tile) and tile not in kinds:
            kinds.append(tile)
    return kinds
