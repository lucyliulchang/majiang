"""碰杠胡的询问窗口（ClaimWindow）与优先级仲裁。

不用"先到先得"：网络抖动会让手快的人拿到本不该属于他的动作。
窗口关闭后统一按 胡 > 碰/杠 > 吃 仲裁，同优先级按打牌者下家优先，保证与网络状况无关、可复现。

v1.1.0「胡牌优先 / 过胡」（改进文档 U-1）：一张牌上"胡"和吃碰杠是**有序的两段决策**——先决定胡不胡，
点了"不胡"（过胡）才补发吃碰杠。过胡只是本窗口的内部状态，不跨窗口、不跨牌，因此不会产生"整局过胡"。

v1.1.0「吃牌选两张」（改进文档 U-2）：`chow_options` 枚举被吃牌作顺子低/中/高三态的全部组合；
`is_chow` 是"客户端指定的两张手牌能不能成顺"的严格口径，供引擎在提交与落地两处校验。
"""

from dataclasses import dataclass, field

PRIORITY = {"hu": 4, "pong": 3, "kong": 2, "chow": 1, "pass": 0}


@dataclass
class ClaimWindow:
    tile: int
    from_seat: int
    # seat -> 该座位可执行的动作列表，例如 [{"action":"pong"},{"action":"chow","tiles":[1,2]}]
    # 一次算全（含胡与吃碰杠），"先只问胡"由 available() 过滤实现
    options: dict[int, list[dict]] = field(default_factory=dict)
    # seat -> 已提交的**终态**动作；过胡不写这里（否则窗口会提前按"放弃全部"收口）
    responses: dict[int, dict] = field(default_factory=dict)
    #: 本窗口内已过胡的座位：不再提供 hu，但仍在等它决定吃碰杠（仅当前这张牌有效）
    passed_hu: set[int] = field(default_factory=set)
    reason: str = "discard"  # "discard" | "rob_kong"
    kong_seat: int | None = None
    kong_kind: str | None = None
    #: 被抢的明杠源自哪一家的弃牌（抢杠不成立时要把那张牌收回并补杠，07 §6.5.4）
    origin_from_seat: int | None = None

    @property
    def seats(self) -> list[int]:
        return sorted(self.options.keys())

    def hu_stage(self, seat: int) -> bool:
        """该座位此刻是否处于"只问胡"的第一段。

        只有"能胡 **且** 还有吃/碰/杠可补"时才分两段：若它除了胡没有别的动作，
        一次"过"就等于把话说完了，没必要让玩家点两次（抢杠窗口即此类）。
        """
        if seat not in self.options or seat in self.responses or seat in self.passed_hu:
            return False
        actions = self.options[seat]
        if not any(option.get("action") == "hu" for option in actions):
            return False
        return any(option.get("action") != "hu" for option in actions)

    def available(self, seat: int) -> list[dict]:
        """该座位这一刻真正可选的动作（快照 `legal.actions` 的唯一来源）。

        - 胡阶段：`[hu, pass]`，吃碰杠先藏起来；
        - 过胡后：其余动作 + `pass`（不再含 hu）；
        - 本来就胡不了（或只有胡）：原样动作 + `pass`；
        - 已提交终态：空列表（等窗口收口，不再让它改主意）。
        """
        if seat not in self.options or seat in self.responses:
            return []
        actions = self.options[seat]
        if self.hu_stage(seat):
            hu = next(option for option in actions if option.get("action") == "hu")
            return [dict(hu), {"action": "pass", "label": "不胡"}]
        rest = [
            dict(option)
            for option in actions
            # 过胡之后这张牌的 hu 就作废了；没胡或没吃碰杠可补的座位仍照原样给
            if not (option.get("action") == "hu" and seat in self.passed_hu)
        ]
        return [*rest, {"action": "pass", "label": "过"}]

    def record(self, seat: int, action: dict, final: bool = False) -> bool:
        """记录一次提交。

        两段式：胡阶段收到 `pass` 只记入 `passed_hu`（不写终态，窗口继续问吃碰杠）；
        其余动作（含过胡之后的第二个 `pass`）才是终态。`final=True` 供超时兜底强制收口。
        """
        if seat not in self.options:
            return False
        if not final and action.get("action") == "pass" and self.hu_stage(seat):
            self.passed_hu.add(seat)
            return True
        self.responses[seat] = action
        return True

    def is_complete(self) -> bool:
        """全员都有**终态**动作才算问完；处于胡阶段的座位仍算未答。"""
        return all(seat in self.responses for seat in self.options)

    def other_hu_pending(self, seat: int) -> bool:
        """除 `seat` 外，是否还有座位仍**可能胡**这张牌（未过胡、未给终态）。

        用于"胡即收口"的短路判断：只要还有别人能胡，就必须等它表态（同优先级要按座位序仲裁）；
        没有别人能胡时，剩下的吃碰杠优先级都低于胡，等它们纯属空等。
        """
        for other in self.pending():
            if other == seat or other in self.passed_hu:
                continue
            if any(option.get("action") == "hu" for option in self.options.get(other) or ()):
                return True
        return False

    def pending(self) -> list[int]:
        """还没给终态答复的座位（含"已过胡、正在看吃碰杠"的座位）。"""
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
    """返回可用吃牌组合（只含手里的两张，不含被吃的那张）。

    被吃牌在一组顺子里可能是**低张、中张或高张**，三态都要枚举（改进文档 U-2）：
    旧实现只枚举"被吃牌居中"的窗口，于是 `234556万` 遇 `4万` 只算得出 `345`、
    `4万` 作低张的 `234` 与作高张的 `456` 全部漏掉。

    `234556万` + `4万` → `[[2万,3万], [3万,5万], [5万,6万]]`（234 / 345 / 456）。
    组合按顺子升序生成，天然去重；再按手里实际可用（每种各 ≥1 张）过滤。
    """
    if not allow_chow or tile >= 27:
        return []
    rank = tile % 9
    base = tile - rank
    combos: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    for low in range(max(0, rank - 2), min(rank, 6) + 1):
        high = low + 2
        if high > 8:  # low 上限已保证，留作防御
            continue
        partners = [base + i for i in (low, low + 1, high) if i != rank]
        if len(partners) != 2:
            continue
        key = (partners[0], partners[1])
        if key in seen:
            continue
        seen.add(key)
        if all(counts[p] > 0 for p in partners):
            combos.append(partners)
    return combos


def chow_tiles(tile: int, partners: list[int]) -> list[int]:
    return sorted([tile, *partners])


def is_chow(tile: int, partners: list[int], counts: list[int]) -> bool:
    """严格判定「这两张手牌能不能和被吃的牌组成顺子」（04 §9.3 `BAD_CHOW` 的唯一口径）。

    四条同时成立才算合法：两张都在数牌里、与被吃牌**同花色**、rank 连续成三张、
    手里每种牌的实际张数够扣（同一张牌选两次就要有两张）。
    旧实现只校验"手里有这张牌"，前端一旦放开自由选牌就会放过非法组合。
    """
    if len(partners) != 2:
        return False
    if not 0 <= tile < 27:
        return False
    for partner in partners:
        if isinstance(partner, bool) or not isinstance(partner, int):
            return False
        if not 0 <= partner < 27 or partner // 9 != tile // 9:
            return False
    ranks = sorted({tile % 9, partners[0] % 9, partners[1] % 9})
    if len(ranks) != 3 or ranks[0] + 1 != ranks[1] or ranks[1] + 1 != ranks[2]:
        return False
    need: dict[int, int] = {}
    for partner in partners:
        need[partner] = need.get(partner, 0) + 1
    return all(counts[partner] >= amount for partner, amount in need.items())
