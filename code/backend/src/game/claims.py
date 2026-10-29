"""碰杠胡的询问窗口（ClaimWindow）与优先级仲裁。

不用"先到先得"：网络抖动会让手快的人拿到本不该属于他的动作。
窗口关闭后统一按 胡 > 碰/杠 > 吃 仲裁，同优先级按打牌者下家优先，保证与网络状况无关、可复现。
"""

from dataclasses import dataclass, field

PRIORITY = {"hu": 4, "pong": 3, "kong": 2, "chow": 1, "pass": 0}


@dataclass
class ClaimWindow:
    tile: int
    from_seat: int
    # seat -> 该座位可执行的动作列表，例如 [{"action":"pong"},{"action":"chow","tiles":[1,2]}]
    options: dict[int, list[dict]] = field(default_factory=dict)
    # seat -> 已提交的动作
    responses: dict[int, dict] = field(default_factory=dict)
    reason: str = "discard"  # "discard" | "rob_kong"
    kong_seat: int | None = None
    kong_kind: str | None = None
    #: 被抢的明杠源自哪一家的弃牌（抢杠不成立时要把那张牌收回并补杠，07 §6.5.4）
    origin_from_seat: int | None = None

    @property
    def seats(self) -> list[int]:
        return sorted(self.options.keys())

    def record(self, seat: int, action: dict) -> bool:
        if seat not in self.options:
            return False
        self.responses[seat] = action
        return True

    def is_complete(self) -> bool:
        return all(seat in self.responses for seat in self.options)

    def pending(self) -> list[int]:
        return [seat for seat in self.options if seat not in self.responses]

    def resolve(self) -> tuple[int, dict] | None:
        """按优先级选出胜出者；无人要牌返回 None。"""
        best: tuple[int, dict] | None = None
        best_rank = 0
        for seat in self._seat_order():
            action = self.responses.get(seat)
            if not action:
                continue
            rank = PRIORITY.get(action.get("action", "pass"), 0)
            if rank > best_rank:
                best_rank = rank
                best = (seat, action)
        return best

    def _seat_order(self) -> list[int]:
        """从打牌者下家开始，按行牌顺序排列，用于同优先级时"近者优先"。"""
        return [(self.from_seat + step) % 4 for step in range(1, 5)]


def chow_options(counts: list[int], tile: int, allow_chow: bool) -> list[list[int]]:
    """返回可用吃牌组合（只含手里的两张，不含被吃的那张）。"""
    if not allow_chow or tile >= 27:
        return []
    rank = tile % 9
    base = tile - rank
    combos: list[list[int]] = []
    for low in range(max(0, rank - 2), rank + 1):
        high = low + 2
        if high > 8:
            continue
        if low == rank or high == rank:
            continue
        partners = [base + i for i in (low, high) if i != rank]
        if len(partners) != 2:
            continue
        if all(counts[p] > 0 for p in partners):
            combos.append(partners)
    return combos


def chow_tiles(tile: int, partners: list[int]) -> list[int]:
    return sorted([tile, *partners])
