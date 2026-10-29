"""对局状态机骨架（四族共用）。

状态：waiting → dealing → discard（该谁出牌）→ claim（碰杠胡询问窗口）→ discard … → settled
所有合法性校验都在这里完成，前端提交的只是"意图"。

本文件是**通用骨架**（03 §3.1）：只依赖牌张、询问窗口、番种折算与结算四个跨族工具，
不认识任何具体规则族的配置类；族的差异通过注入的 `rule` 对象（鸭子类型）与
`game/families/{engineCode}/engine.py` 的适配层表达。

对局流程口径（03 §3.4–3.6，四族完全一致）：
- 抽座：每圈首局掷 2 骰定东位/庄家，圈内 4 局不重抽；
- 轮庄与局风：第 n 局庄家 = 座位 (n-1) % 4，局风 = 第 n 局 → 东/南/西/北；
- 发牌：每人 4 张 × 3 轮 = 12 张，庄家跳牌取序列第 1、第 5 张（14 张），闲家 13 张；
- 荒庄二分：牌墙取尽无胡 —— 本局有杠 → 记荒庄、迁庄、计局；无杠 → 重发本局、不计数。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from game.claims import ClaimWindow, chow_options, chow_tiles
from game.fan import ScoreBreakdown, best_win
from game.hand import HandContext, Meld, lack_suit_satisfied
from game.patterns import collect_wins, winning_tiles
from game.scoring import kong_delta, settle_draw, default_win_delta
from game.tiles import (
    TILE_SET_136,
    empty_counts,
    new_wall,
    tile_kinds_of,
    tile_name,
    tiles_from_counts,
)

#: 一圈固定 4 个庄次（北位下庄即圈结束，03 §3.4）
MAX_ROUNDS = 4
#: 每家每轮 4 张（2 墩），共发 3 轮
DEAL_TILES_PER_PASS = 4
DEAL_PASSES = 3


class EngineError(Exception):
    """带中文提示的规则异常，直接回给前端。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class SeatState:
    seat: int
    # 账号服务身份是 loginID 字符串（04 §11：user_id(int) → login_id(string)）
    login_id: str
    display_name: str
    color: str
    counts: list[int] = field(default_factory=empty_counts)
    melds: list[Meld] = field(default_factory=list)
    discards: list[int] = field(default_factory=list)
    total_score: int = 0
    round_score: int = 0


@dataclass
class SettledRound:
    """一局结算（03 §3.2 `RoundSettlement`）。

    `winners` 兼容单赢家（通用/广东/柏氏，长度 0/1）与多赢家（四川血战，长度 0..3）：
    多赢家时 `winners_list` 非空、`winner_seat` 取第一个赢家（落库 `winnerSeat` 口径）。
    """

    round_no: int
    dealer_seat: int
    winner_seat: int | None
    win_type: str
    winning_tile: int | None
    pattern_id: str | None
    fan_items: list[dict]
    fan_total: int
    score_delta: list[int]
    breakdown: dict | None
    # ---- S6 追加字段（快照/落库只增不删，03 §11）----
    round_wind: int = 0
    fan_raw: int = 0
    fan_cap: int | None = None
    kong_delta: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    is_draw: bool = False
    restarts: int = 0
    # ---- S7 追加字段 ----
    winners_list: list[dict] = field(default_factory=list)
    payer_allocation: list[dict] = field(default_factory=list)
    multipliers: dict = field(default_factory=lambda: {"self_draw": 1, "dealer": 1})
    summary_text: str = ""
    #: 终局四家手牌与副露（落库 `finalHandsJson`，供战绩回放核对番种）
    final_hands: list[dict] = field(default_factory=list)

    @property
    def winners(self) -> list[dict]:
        """统一结构：单赢家长度 1，荒庄为空，四川血战可到 3（03 §3.2）。"""
        if self.winners_list:
            return self.winners_list
        if self.winner_seat is None:
            return []
        return [
            {
                "seat": self.winner_seat,
                "win_type": self.win_type,
                "winning_tile": self.winning_tile,
                "pattern_id": self.pattern_id,
                "fan_items": self.fan_items,
                "fan_raw": self.fan_raw,
                "fan_cap": self.fan_cap,
                "fan_total": self.fan_total,
                "multipliers": dict(self.multipliers),
                "score_from_fan": self.breakdown.get("score", 0) if self.breakdown else 0,
                "breakdown": self.breakdown,
            }
        ]


def final_hands_snapshot(states: list["SeatState"], winners: list[dict]) -> list[dict]:
    """终局四家手牌与副露（落库 `finalHandsJson`，供战绩回放核对番种）。

    点炮胡 / 抢杠胡的胡张不在 `counts` 里（只在 HandContext.extra_tile），按赢家补进去；
    自摸时 `counts` 已含胡张。暗杠也按真实牌面留痕——战绩详情只对本家成员开放。
    """
    win_map: dict[int, dict] = {}
    for item in winners:
        try:
            win_map[int(item.get("seat"))] = item
        except (TypeError, ValueError):
            continue
    result: list[dict] = []
    for state in states:
        tiles = tiles_from_counts(state.counts)
        info = win_map.get(state.seat)
        if info is not None:
            tile = info.get("winning_tile")
            if tile is not None and info.get("win_type") != "self_draw":
                tiles.append(int(tile))
                tiles.sort()
        result.append(
            {
                "seat": state.seat,
                "login_id": state.login_id,
                "display_name": state.display_name,
                "concealed": tiles,
                "melds": [meld.to_dict(reveal=True) for meld in state.melds],
                "is_winner": info is not None,
                "win_type": (info or {}).get("win_type"),
                "winning_tile": (info or {}).get("winning_tile"),
            }
        )
    return result


def _order_after(seat: int) -> list[int]:
    return [(seat + step) % 4 for step in range(1, 4)]


def dealer_of_round(round_no: int) -> int:
    """第 n 局庄家 = 座位 (n-1) % 4（03 §3.4：每局换庄，不设连庄）。"""
    return (max(1, int(round_no)) - 1) % MAX_ROUNDS


def round_wind_of(round_no: int) -> int:
    """局风 = 局序 - 1：第 1 局东、第 2 局南、第 3 局西、第 4 局北（与谁是庄家无关）。"""
    return (max(1, int(round_no)) - 1) % MAX_ROUNDS


def roll_dice(rng: random.Random | None = None) -> list[int]:
    """掷 2 颗骰子。"""
    source = rng or random.SystemRandom()
    return [source.randint(1, 6), source.randint(1, 6)]


def draw_seats(login_ids: list[str], rng: random.Random | None = None) -> dict:
    """抽座（03 §3.4）：每圈首局执行一次，圈内 4 局不重抽。

    ① 四人各抽一张风签（东南西北各一张）定物理座位；
    ② 四人依次各掷 2 颗骰子，点数和最大者坐 座位 0（东位）并坐庄，
       若其抽到的不是东位则与东位玩家交换座位；
    ③ 同点按先掷者优先（「先为东」）；仍并列最高则并列者重掷到唯一最大。

    返回 `{dealer_seat, assignments:[{seat, login_id, dice}]}`，`assignments` 按座位 0→3 排序。
    """
    if len(login_ids) != 4:
        raise EngineError("BAD_SEATS", "抽座需要正好 4 位玩家")
    source = rng or random.SystemRandom()

    lots = [0, 1, 2, 3]  # 0=东 1=南 2=西 3=北，抽签结果即物理座位
    source.shuffle(lots)
    # 抽签顺序 = login_ids 顺序；lot_seat[login] = 抽到的座位
    lot_seat: dict[str, int] = {login: lots[index] for index, login in enumerate(login_ids)}
    at_seat: dict[int, str] = {seat: login for login, seat in lot_seat.items()}

    # 依次按物理座位 0→3 掷骰，记录每人的点数（骰子属于人）
    dice_of: dict[str, list[int]] = {}
    for seat in range(4):
        dice_of[at_seat[seat]] = roll_dice(source)

    def total_of(login: str) -> int:
        return sum(dice_of[login])

    # 先掷者优先：座位号小者先掷，同点取先掷者
    contenders = [at_seat[seat] for seat in range(4)]
    best = max(contenders, key=lambda login: (total_of(login), -contenders.index(login)))
    tied = [login for login in contenders if total_of(login) == total_of(best)]
    if len(tied) > 1:
        # 并列最高：并列者重掷到唯一最大
        while len(tied) > 1:
            for login in tied:
                dice_of[login] = roll_dice(source)
            top = max(total_of(login) for login in tied)
            tied = [login for login in tied if total_of(login) == top]
        best = tied[0]

    # 最大者坐东位（座位 0）；若抽到的不是东位，与东位玩家交换座位
    east_login = at_seat[0]
    if best != east_login:
        lot_seat[best], lot_seat[east_login] = 0, lot_seat[best]
        at_seat = {seat: login for login, seat in lot_seat.items()}

    assignments = [
        {"seat": seat, "login_id": at_seat[seat], "dice": list(dice_of[at_seat[seat]])}
        for seat in range(4)
    ]
    return {"dealer_seat": 0, "assignments": assignments}


class GameEngine:
    """通用状态机骨架。族通过 `rule` 对象注入参数，通过子类/工厂注入差异。"""

    family_code = "generic"
    tile_set_code = TILE_SET_136

    def __init__(
        self,
        rule,
        seats: list[SeatState],
        round_no: int = 1,
        dealer_seat: int | None = None,
        round_wind: int | None = None,
        rng: random.Random | None = None,
    ):
        self.rule = rule
        self.seats: dict[int, SeatState] = {item.seat: item for item in seats}
        self.round_no = round_no
        # 第 n 局庄家 = 座位 n-1，局风 = 第 n 局（03 §3.4）；显式传入时以传入值为准
        self.dealer_seat = dealer_of_round(round_no) if dealer_seat is None else dealer_seat
        self.round_wind = round_wind_of(round_no) if round_wind is None else round_wind
        self.rng = rng

        self.wall: list[int] = []
        self.front = 0
        self.back = -1
        self.turn = self.dealer_seat
        self.phase = "waiting"
        self.last_draw: int | None = None
        self.after_kong = False
        self.last_discard: int | None = None
        self.last_discard_seat: int | None = None
        self.claim: ClaimWindow | None = None
        self.kong_accumulated: list[int] = [0, 0, 0, 0]
        # 本局是否发生过杠：决定牌墙取尽后是「荒庄」还是「重发」（03 §3.6）
        self.kong_happened = False
        self.restarts = 0
        self.deal: dict = {}
        self.result: SettledRound | None = None
        # ---- S7：时效判定（天胡/地胡，07 §6.5）所需的局面计数 ----
        self.move_count = 0  # 本局出牌次数（0 = 牌墙未动）
        self.draws_by_seat: dict[int, int] = {seat: 0 for seat in range(MAX_ROUNDS)}
        self.claim_happened = False  # 本局是否发生过吃/碰/明杠

    # ------------------------------------------------------------------ 基础
    @property
    def tile_set(self) -> tuple[int, ...]:
        return tuple(range(tile_kinds_of(self.tile_set_code)))

    @property
    def remaining(self) -> int:
        return max(0, self.back - self.front + 1)

    def seat_state(self, seat: int) -> SeatState:
        state = self.seats.get(seat)
        if state is None:
            raise EngineError("NO_SEAT", "该座位没有玩家")
        return state

    def seat_wind(self, seat: int) -> int:
        """门风 = (座位 - 庄家座位) % 4：庄家恒为东风，逐局整体转动。"""
        return (seat - self.dealer_seat) % 4

    def _ctx(
        self,
        seat: int,
        win_tile: int | None = None,
        is_self_draw: bool = True,
        is_robbing_kong: bool = False,
        extra_tile: int | None = None,
    ) -> HandContext:
        state = self.seat_state(seat)
        counts = list(state.counts)
        if extra_tile is not None:
            counts[extra_tile] += 1
        is_heavenly = (
            is_self_draw
            and seat == self.dealer_seat
            and self.move_count == 0
            and not self.claim_happened
        )
        is_earthly = (
            is_self_draw
            and seat != self.dealer_seat
            and self.draws_by_seat.get(seat, 0) == 1
            and not self.claim_happened
        )
        return HandContext(
            counts=counts,
            melds=list(state.melds),
            win_tile=win_tile,
            is_self_draw=is_self_draw,
            seat_wind=self.seat_wind(seat),
            round_wind=self.round_wind,
            is_last_tile=self.remaining == 0,
            is_robbing_kong=is_robbing_kong,
            is_after_kong=self.after_kong,
            is_heavenly=is_heavenly,
            is_earthly=is_earthly,
        )

    # ------------------------------------------------------------------ 族钩子
    def _min_fan_to_win(self) -> int:
        """起胡番数（03 §2.2 `min_fan_to_win`）；通用/广东/四川为 0，柏氏为 1。"""
        try:
            return max(0, int(getattr(self.rule, "min_fan_to_win", 0) or 0))
        except (TypeError, ValueError):
            return 0

    def _requires_lack_suit(self) -> bool:
        """是否强制缺一门（四川）；其余族恒 False（03 §8）。"""
        return bool(getattr(self.rule, "lack_suit_required", False))

    def _rob_kong_kinds(self) -> tuple[str, ...]:
        """可被抢杠的杠型：通用族仅补杠；柏氏仅明杠（07 §6.5.4）。"""
        kinds = getattr(self.rule, "rob_kong_kinds", ("added",))
        return tuple(kinds or ())

    def _out_seats(self) -> set[int]:
        """已退出本局的座位（血战到底用；单赢家族恒为空）。"""
        return set()

    def _next_active(self, seat: int) -> int:
        """下一个可行动座位：单赢家族就是下家（03 §3.4 的行牌顺序）。"""
        return (seat + 1) % MAX_ROUNDS

    def _kong_delta(self, seat: int, kind: str, from_seat: int | None) -> list[int]:
        """杠分（族可改付款方：柏氏三类杠恒为三家各付，07 §8）。"""
        return kong_delta(self.rule, seat, kind, from_seat)

    def _settle_fan_delta(
        self,
        winner_seat: int,
        breakdown: ScoreBreakdown,
        win_type: str,
        discard_seat: int | None,
        ctx: HandContext | None = None,
    ) -> tuple[list[int], list[dict], dict]:
        """把一家的番分折算成四家分差；返回 `(分差, payer_allocation, 生效倍率)`。

        `ctx` 是胡牌那一刻的手牌上下文，族算包牌/倍数时会用到（通用族忽略）。
        """
        _ = ctx
        score = int(getattr(breakdown, "score", 0) or 0)
        is_self_draw = win_type == "self_draw"
        delta = default_win_delta(self.rule, winner_seat, is_self_draw, discard_seat, score)
        return delta, [], {"self_draw": 1, "dealer": 1}

    def evaluate_win(self, ctx: HandContext) -> ScoreBreakdown | None:
        """族级胡牌判定：牌型命中 + 缺一门 + 起胡番数三道闸门。

        返回 `None` 即「不能胡」，避免各处分别调用 `is_winning` 而漏掉族约束。
        """
        wins = collect_wins(ctx, self.rule)
        if not wins:
            return None
        breakdown = best_win(wins, self.rule)
        if breakdown is None:
            return None
        if self._requires_lack_suit() and not lack_suit_satisfied(ctx):
            return None
        if breakdown.fan_total < self._min_fan_to_win():
            return None
        return breakdown

    # ------------------------------------------------------------------ 开局
    def start_round(
        self, dealer_seat: int | None = None, round_wind: int | None = None
    ) -> list[dict]:
        """洗牌 → 掷骰定开牌点 → 发牌（4×3 + 跳牌）→ 庄家直接出牌。"""
        if dealer_seat is not None:
            self.dealer_seat = dealer_seat
        if round_wind is not None:
            self.round_wind = round_wind

        self.phase = "dealing"
        self.result = None
        self.claim = None
        self.kong_accumulated = [0, 0, 0, 0]
        self.kong_happened = False
        self.last_discard = None
        self.last_discard_seat = None
        self.after_kong = False
        self.move_count = 0
        self.draws_by_seat = {seat: 0 for seat in range(MAX_ROUNDS)}
        self.claim_happened = False

        for state in self.seats.values():
            state.counts = empty_counts()
            state.melds = []
            state.discards = []
            state.round_score = 0

        self.wall = new_wall(self.rng, self.tile_set_code)
        dice = roll_dice(self.rng)
        total = dice[0] + dice[1]
        # 从庄家起数 total 家得开牌家（庄家算第 1 家）
        break_seat = (self.dealer_seat + total - 1) % 4
        self.wall = self._break_wall(self.wall, break_seat, total)
        self.front = 0
        self.back = len(self.wall) - 1
        self.deal = {"dice": dice, "break_seat": break_seat, "break_stack": total}

        order = [(self.dealer_seat + step) % 4 for step in range(4)]
        for _ in range(DEAL_PASSES):
            for seat in order:
                for _ in range(DEAL_TILES_PER_PASS):
                    tile = self._draw_front()
                    if tile is None:
                        break
                    self.seat_state(seat).counts[tile] += 1

        # 跳牌：庄家取第 1、第 5 张；下家、对家、上家依次取第 2、3、4 张
        jump = [self._draw_front() for _ in range(5)]
        if all(tile is not None for tile in jump):
            self.seat_state(order[0]).counts[jump[0]] += 1
            self.seat_state(order[0]).counts[jump[4]] += 1
            for index, seat in enumerate(order[1:], start=1):
                self.seat_state(seat).counts[jump[index]] += 1

        self.turn = self.dealer_seat
        self.phase = "discard"
        # 首轮庄家不摸牌，直接出牌；下发的 drawn 是跳牌的第 5 张
        self.last_draw = jump[4] if all(tile is not None for tile in jump) else None

        return [
            {
                "type": "event.round_started",
                "data": {
                    "round_no": self.round_no,
                    "dealer_seat": self.dealer_seat,
                    "round_wind": self.round_wind,
                    "wall_count": self.remaining,
                    "deal": dict(self.deal),
                },
            },
            self._turn_event(),
        ]

    def _break_wall(self, wall: list[int], break_seat: int, stacks: int) -> list[int]:
        """按开牌点把牌墙排成取牌序列（首尾相接，尾部为补牌端与海底判定端）。

        牌墙按座位分成 4 段（136 张每段 34 张 = 17 墩）：从开牌家牌墙**右端**数 `stacks` 墩，
        其后一墩为开牌点，自该点按座位顺序续接成取牌序列。
        """
        segment_size = len(wall) // 4
        stacks_per_segment = max(1, segment_size // 2)
        offset_stacks = max(0, stacks_per_segment - min(stacks, stacks_per_segment))
        offset = min(offset_stacks * 2, segment_size - 1)
        start = break_seat * segment_size
        head = wall[start : start + segment_size]
        sequence = head[offset:] + head[:offset]
        for step in range(1, 4):
            left = ((break_seat + step) % 4) * segment_size
            sequence.extend(wall[left : left + segment_size])
        return sequence

    def _draw_front(self) -> int | None:
        if self.front > self.back:
            return None
        tile = self.wall[self.front]
        self.front += 1
        return tile

    def _draw_back(self) -> int | None:
        if self.back < self.front:
            return None
        tile = self.wall[self.back]
        self.back -= 1
        return tile

    # ------------------------------------------------------------------ 查询
    def legal_actions(self, seat: int) -> dict:
        if self.phase == "claim" and self.claim and seat in self.claim.options:
            return {
                "actions": self.claim.options[seat],
                "claim_tile": self.claim.tile,
                "claim_from": self.claim.from_seat,
                "reason": self.claim.reason,
            }
        if self.phase == "discard" and seat == self.turn:
            actions: list[dict] = [{"action": "discard"}]
            if self.evaluate_win(self._ctx(seat, win_tile=self.last_draw)) is not None:
                actions.append({"action": "hu"})
            actions.extend(self._self_kong_options(seat))
            return {"actions": actions}
        return {"actions": []}

    def _self_kong_options(self, seat: int) -> list[dict]:
        state = self.seat_state(seat)
        options: list[dict] = []
        for tile, count in enumerate(state.counts):
            if count == 4:
                options.append(
                    {"action": "kong", "kong_kind": "hidden", "tiles": [tile], "label": f"暗杠{tile_name(tile)}"}
                )
        for meld in state.melds:
            if meld.kind == "pong" and state.counts[meld.tiles[0]] >= 1:
                tile = meld.tiles[0]
                options.append(
                    {"action": "kong", "kong_kind": "added", "tiles": [tile], "label": f"补杠{tile_name(tile)}"}
                )
        return options

    def tenpai_map(self, seat: int) -> dict[int, list[int]]:
        """打掉每张牌之后的听牌情况，仅规则开启听牌提示时由上层调用。"""
        state = self.seat_state(seat)
        result: dict[int, list[int]] = {}
        for tile, count in enumerate(state.counts):
            if count <= 0:
                continue
            state.counts[tile] -= 1
            waits = winning_tiles(self._ctx(seat), self.rule)
            state.counts[tile] += 1
            if waits:
                result[tile] = waits
        return result

    def snapshot_options(self) -> dict:
        """下发到牌桌快照的生效选项：开关关闭时只给 enabled，不给从属值（03 §10）。"""
        rule = self.rule
        options: dict = {
            "rounds_per_game": getattr(rule, "rounds_per_game", MAX_ROUNDS),
            "claim_window_seconds": getattr(rule, "claim_window_seconds", 8),
            "allow_chow": bool(getattr(rule, "allow_chow", True)),
        }
        timeout = getattr(rule, "turn_timeout", None)
        if timeout is not None:
            options["turn_timeout"] = (
                {"enabled": True, "seconds": timeout.seconds}
                if timeout.enabled
                else {"enabled": False}
            )
        kong = getattr(rule, "kong_score", None)
        if kong is not None:
            options["kong_score"] = (
                {"enabled": True, "exposed": kong.exposed, "hidden": kong.hidden, "added": kong.added}
                if kong.enabled
                else {"enabled": False}
            )
        ting = getattr(rule, "ting_hint", None)
        if ting is not None:
            options["ting_hint"] = {"enabled": bool(ting.enabled)}
        draw = getattr(rule, "draw_penalty", None)
        if draw is not None:
            options["draw_penalty"] = (
                {"enabled": True, "value": draw.value or 0} if draw.enabled else {"enabled": False}
            )
        return options

    def settlement(self) -> dict | None:
        """03 §3.2 的统一结算结构（通用族恒为单赢家）。"""
        if self.result is None:
            return None
        settled = self.result
        return {
            "round_no": settled.round_no,
            "dealer_seat": settled.dealer_seat,
            "round_wind": settled.round_wind,
            "winners": settled.winners,
            "score_delta": list(settled.score_delta),
            "payer_allocation": list(settled.payer_allocation),
            "kong_delta": list(settled.kong_delta),
            "multipliers": dict(settled.multipliers),
            "summary": settled.summary_text or self._summary_text(settled),
            "is_draw": settled.is_draw,
        }

    def _summary_text(self, settled: SettledRound) -> str:
        breakdown = settled.breakdown or {}
        pattern_name = str(breakdown.get("pattern_name") or "")
        lines = breakdown.get("lines") or []
        parts = [f"{line['name']} {line['fan']}" for line in lines if line.get("fan")]
        if pattern_name and parts:
            return f"{pattern_name}：" + " + ".join(parts)
        return pattern_name

    # ------------------------------------------------------------------ 动作
    def apply_action(self, seat: int, action: dict) -> list[dict]:
        if self.phase == "settled":
            raise EngineError("ROUND_OVER", "本局已经结束了")
        kind = action.get("action")
        if not kind:
            raise EngineError("BAD_ACTION", "缺少动作类型")

        if self.phase == "claim":
            return self._claim_response(seat, action)

        if self.phase != "discard" or seat != self.turn:
            raise EngineError("NOT_YOUR_TURN", "还没轮到你操作")

        if kind == "discard":
            return self._do_discard(seat, action)
        if kind == "hu":
            return self._do_self_draw_hu(seat)
        if kind == "kong":
            return self._do_self_kong(seat, action)
        raise EngineError("BAD_ACTION", f"现在不能执行「{kind}」")

    def _do_discard(self, seat: int, action: dict) -> list[dict]:
        tiles = action.get("tiles") or []
        if len(tiles) != 1:
            raise EngineError("BAD_DISCARD", "出牌必须且只能选一张")
        tile = tiles[0]
        state = self.seat_state(seat)
        if not 0 <= tile < 34 or state.counts[tile] <= 0:
            raise EngineError("NOT_IN_HAND", "这张牌不在你手里")
        if tile not in self.tile_set:
            # 108 张族（四川）无字牌：手里不该有，提交上来按非法出牌拒绝
            raise EngineError("BAD_DISCARD", f"当前牌张集合里没有「{tile_name(tile)}」")

        state.counts[tile] -= 1
        state.discards.append(tile)
        self.last_discard = tile
        self.last_discard_seat = seat
        self.after_kong = False
        self.last_draw = None
        self.move_count += 1

        events = [{"type": "event.discarded", "data": {"seat": seat, "tile": tile}}]
        window = self._build_claim_window(tile, seat, reason="discard")
        if window is None:
            events.extend(self._begin_turn(self._next_active(seat)))
            return events
        self.claim = window
        self.phase = "claim"
        events.append(
            {
                "type": "event.claim_open",
                "data": {
                    "tile": tile,
                    "from_seat": seat,
                    "seats": window.seats,
                    "reason": window.reason,
                },
            }
        )
        return events

    def _build_claim_window(
        self,
        tile: int,
        from_seat: int,
        reason: str = "discard",
        exclude: set[int] | None = None,
    ) -> ClaimWindow | None:
        options: dict[int, list[dict]] = {}
        out_seats = self._out_seats()
        for seat in _order_after(from_seat):
            if seat in out_seats or seat in (exclude or ()):
                continue
            state = self.seat_state(seat)
            actions: list[dict] = []
            if reason == "discard":
                if self.evaluate_win(
                    self._ctx(seat, win_tile=tile, is_self_draw=False, extra_tile=tile)
                ) is not None:
                    actions.append({"action": "hu", "label": "胡"})
                if state.counts[tile] >= 3:
                    actions.append({"action": "kong", "kong_kind": "exposed", "tiles": [tile], "label": "明杠"})
                if state.counts[tile] >= 2:
                    actions.append({"action": "pong", "tiles": [tile, tile], "label": "碰"})
                if seat == (from_seat + 1) % 4:
                    for combo in chow_options(state.counts, tile, self.rule.allow_chow):
                        actions.append(
                            {
                                "action": "chow",
                                "tiles": combo,
                                "label": f"吃（用{tile_name(combo[0])}{tile_name(combo[1])}）",
                            }
                        )
            else:
                if self.evaluate_win(
                    self._ctx(
                        seat,
                        win_tile=tile,
                        is_self_draw=False,
                        is_robbing_kong=True,
                        extra_tile=tile,
                    )
                ) is not None:
                    actions.append({"action": "hu", "label": "抢杠胡"})
            if actions:
                options[seat] = actions
        if not options:
            return None
        return ClaimWindow(tile=tile, from_seat=from_seat, options=options, reason=reason)

    def _claim_response(self, seat: int, action: dict) -> list[dict]:
        window = self.claim
        if window is None:
            raise EngineError("NO_CLAIM", "当前没有可响应的牌")
        if seat not in window.options:
            raise EngineError("NOT_YOUR_CALL", "这张牌你没法操作")
        kind = action.get("action")
        if kind not in ("pass", "hu", "pong", "kong", "chow"):
            raise EngineError("BAD_ACTION", "这里只能过、胡、碰、杠或者吃")
        if kind != "pass" and not any(
            option["action"] == kind for option in window.options[seat]
        ):
            raise EngineError("BAD_ACTION", f"这张牌你不能「{kind}」")

        window.record(seat, {"action": kind, "tiles": action.get("tiles", [])})
        if not window.is_complete():
            return []
        return self._resolve_claim()

    def timeout_claim(self) -> list[dict]:
        """询问窗口超时：未响应的座位按"过"处理。"""
        if self.phase != "claim" or self.claim is None:
            return []
        for seat in self.claim.pending():
            self.claim.record(seat, {"action": "pass"})
        return self._resolve_claim()

    def _resolve_claim(self) -> list[dict]:
        window = self.claim
        if window is None:
            return []
        self.claim = None
        chosen = window.resolve()

        if chosen is None:
            if window.reason == "rob_kong" and window.kong_seat is not None:
                return self._finish_rob_kong_window(window)
            return self._begin_turn(self._next_active(window.from_seat))

        seat, action = chosen
        kind = action["action"]
        if kind == "hu":
            if window.reason == "rob_kong" and window.kong_seat is not None:
                return self._settle_rob_kong(seat, window.kong_seat, window.tile)
            return self._settle_discard_hu(seat, window.from_seat, window.tile)
        if kind == "pong":
            return self._do_pong(seat, window)
        if kind == "kong":
            return self._do_exposed_kong(seat, window)
        if kind == "chow":
            return self._do_chow(seat, window, action.get("tiles") or [])
        raise EngineError("BAD_ACTION", "无法识别的动作")

    # ------------------------------------------------------------------ 吃碰杠
    def _take_from_river(self, from_seat: int, tile: int) -> None:
        river = self.seat_state(from_seat).discards
        if river and river[-1] == tile:
            river.pop()

    def _do_pong(self, seat: int, window: ClaimWindow) -> list[dict]:
        state = self.seat_state(seat)
        tile = window.tile
        state.counts[tile] -= 2
        state.melds.append(
            Meld(kind="pong", tiles=[tile, tile, tile], from_seat=window.from_seat, claim_tile=tile)
        )
        self._take_from_river(window.from_seat, tile)
        self.claim_happened = True
        self.turn = seat
        self.phase = "discard"
        self.after_kong = False
        self.last_draw = None
        return [
            {
                "type": "event.claimed",
                "data": {"seat": seat, "from_seat": window.from_seat, "action": "pong", "tile": tile},
            },
            self._turn_event(),
        ]

    def _do_chow(self, seat: int, window: ClaimWindow, partners: list[int]) -> list[dict]:
        state = self.seat_state(seat)
        if len(partners) != 2 or any(state.counts[p] <= 0 for p in partners):
            raise EngineError("BAD_CHOW", "吃牌的组合不合法")
        for partner in partners:
            state.counts[partner] -= 1
        state.melds.append(
            Meld(
                kind="chow",
                tiles=chow_tiles(window.tile, partners),
                from_seat=window.from_seat,
                claim_tile=window.tile,
            )
        )
        self._take_from_river(window.from_seat, window.tile)
        self.claim_happened = True
        self.turn = seat
        self.phase = "discard"
        self.after_kong = False
        self.last_draw = None
        return [
            {
                "type": "event.claimed",
                "data": {
                    "seat": seat,
                    "from_seat": window.from_seat,
                    "action": "chow",
                    "tile": window.tile,
                    "tiles": chow_tiles(window.tile, partners),
                },
            },
            self._turn_event(),
        ]

    def _do_exposed_kong(
        self, seat: int, window: ClaimWindow, allow_rob: bool = True
    ) -> list[dict]:
        """明杠（大明杠）：族声明「明杠可抢」时先开抢杠窗口（07 §6.5.4）。"""
        tile = window.tile
        if allow_rob and "exposed" in self._rob_kong_kinds():
            # 杠家本人不参与抢杠询问（07 §6.5.4：其他家才可抢）
            rob = self._build_claim_window(
                tile, window.from_seat, reason="rob_kong", exclude={seat}
            )
            if rob is not None:
                rob.kong_seat = seat
                rob.kong_kind = "exposed"
                rob.origin_from_seat = window.from_seat
                self.claim = rob
                self.phase = "claim"
                return [
                    {
                        "type": "event.claim_open",
                        "data": {
                            "tile": tile,
                            "from_seat": seat,
                            "seats": rob.seats,
                            "reason": "rob_kong",
                        },
                    }
                ]

        state = self.seat_state(seat)
        state.counts[tile] -= 3
        state.melds.append(
            Meld(kind="kong_exposed", tiles=[tile] * 4, from_seat=window.from_seat, claim_tile=tile)
        )
        self._take_from_river(window.from_seat, tile)
        self.kong_happened = True
        self.claim_happened = True
        events = [
            {
                "type": "event.kongged",
                "data": {"seat": seat, "kind": "exposed", "tile": tile, "from_seat": window.from_seat},
            }
        ]
        events.extend(self._award_kong(seat, "exposed", window.from_seat))
        events.extend(self._begin_turn(seat, from_tail=True))
        return events

    def _finish_rob_kong_window(self, window: ClaimWindow) -> list[dict]:
        """抢杠窗口无人抢：杠成立并计杠分，杠家从牌尾补牌。"""
        assert window.kong_seat is not None
        seat = window.kong_seat
        if window.kong_kind == "exposed":
            replay = ClaimWindow(
                tile=window.tile,
                from_seat=window.origin_from_seat if window.origin_from_seat is not None else seat,
                options={},
                reason="discard",
            )
            events = self._do_exposed_kong(seat, replay, allow_rob=False)
        else:
            events = self._apply_added_kong(seat, window.tile)
        events.extend(self._begin_turn(seat, from_tail=True))
        return events

    def _do_self_kong(self, seat: int, action: dict) -> list[dict]:
        state = self.seat_state(seat)
        kong_kind = action.get("kong_kind")
        tiles = action.get("tiles") or []
        if not tiles:
            raise EngineError("BAD_KONG", "没有指定要杠的牌")
        tile = tiles[0]

        if kong_kind == "hidden":
            if state.counts[tile] != 4:
                raise EngineError("BAD_KONG", "暗杠需要手里正好有 4 张相同的牌")
            state.counts[tile] = 0
            state.melds.append(Meld(kind="kong_hidden", tiles=[tile] * 4))
            self.kong_happened = True
            events = [
                {"type": "event.kongged", "data": {"seat": seat, "kind": "hidden", "tile": tile}}
            ]
            events.extend(self._award_kong(seat, "hidden", None))
            events.extend(self._begin_turn(seat, from_tail=True))
            return events

        if kong_kind == "added":
            if not any(m.kind == "pong" and m.tiles[0] == tile for m in state.melds):
                raise EngineError("BAD_KONG", "补杠需要先碰过这张牌")
            if state.counts[tile] < 1:
                raise EngineError("NOT_IN_HAND", "这张牌不在你手里")
            # 补杠是否可抢由族定义：通用族可抢；柏氏不可抢，直接成立（07 §6.5.4）
            if "added" in self._rob_kong_kinds():
                window = self._build_claim_window(tile, seat, reason="rob_kong")
                if window is not None:
                    window.kong_seat = seat
                    window.kong_kind = "added"
                    self.claim = window
                    self.phase = "claim"
                    return [
                        {
                            "type": "event.claim_open",
                            "data": {
                                "tile": tile,
                                "from_seat": seat,
                                "seats": window.seats,
                                "reason": "rob_kong",
                            },
                        }
                    ]
            events = self._apply_added_kong(seat, tile)
            events.extend(self._begin_turn(seat, from_tail=True))
            return events

        raise EngineError("BAD_KONG", "杠的类型不合法")

    def _apply_added_kong(self, seat: int, tile: int) -> list[dict]:
        state = self.seat_state(seat)
        state.counts[tile] -= 1
        for index, meld in enumerate(state.melds):
            if meld.kind == "pong" and meld.tiles[0] == tile:
                state.melds[index] = Meld(
                    kind="kong_added",
                    tiles=[tile] * 4,
                    from_seat=meld.from_seat,
                    claim_tile=meld.claim_tile,
                )
                break
        self.kong_happened = True
        events = [{"type": "event.kongged", "data": {"seat": seat, "kind": "added", "tile": tile}}]
        events.extend(self._award_kong(seat, "added", None))
        return events

    def _award_kong(self, seat: int, kind: str, from_seat: int | None) -> list[dict]:
        self.kong_happened = True
        delta = self._kong_delta(seat, kind, from_seat)
        for index, value in enumerate(delta):
            self.kong_accumulated[index] += value
            self.seat_state(index).round_score += value
        if not any(delta):
            return []
        return [
            {
                "type": "event.kong_score",
                "data": {
                    "seat": seat,
                    "kind": kind,
                    "delta": delta,
                    "enabled": self.rule.kong_score.enabled,
                },
            }
        ]

    # ------------------------------------------------------------------ 摸牌
    def _begin_turn(self, seat: int, from_tail: bool = False) -> list[dict]:
        tile = self._draw_back() if from_tail else self._draw_front()
        if tile is None:
            return self._settle_draw()
        state = self.seat_state(seat)
        state.counts[tile] += 1
        self.turn = seat
        self.phase = "discard"
        self.last_draw = tile
        self.after_kong = from_tail
        self.draws_by_seat[seat] = self.draws_by_seat.get(seat, 0) + 1
        return [
            {"type": "event.drawn", "data": {"seat": seat, "wall_count": self.remaining}},
            self._turn_event(),
        ]

    def _turn_event(self) -> dict:
        return {
            "type": "event.turn_changed",
            "data": {
                "seat": self.turn,
                "phase": self.phase,
                "wall_count": self.remaining,
                "after_kong": self.after_kong,
            },
        }

    # ------------------------------------------------------------------ 结算
    def _do_self_draw_hu(self, seat: int) -> list[dict]:
        ctx = self._ctx(seat, win_tile=self.last_draw, is_self_draw=True)
        breakdown = self.evaluate_win(ctx)
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡")
        return self._finish_win(seat, "self_draw", self.last_draw, breakdown, None, ctx)

    def _settle_discard_hu(self, seat: int, from_seat: int, tile: int) -> list[dict]:
        ctx = self._ctx(seat, win_tile=tile, is_self_draw=False, extra_tile=tile)
        breakdown = self.evaluate_win(ctx)
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡")
        return self._finish_win(seat, "discard", tile, breakdown, from_seat, ctx)

    def _settle_rob_kong(self, seat: int, kong_seat: int, tile: int) -> list[dict]:
        ctx = self._ctx(
            seat, win_tile=tile, is_self_draw=False, is_robbing_kong=True, extra_tile=tile
        )
        breakdown = self.evaluate_win(ctx)
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡")
        return self._finish_win(seat, "rob_kong", tile, breakdown, kong_seat, ctx)

    def _finish_win(
        self,
        seat: int,
        win_type: str,
        tile: int | None,
        breakdown: ScoreBreakdown,
        discard_seat: int | None,
        ctx: HandContext | None = None,
    ) -> list[dict]:
        """一家胡牌的收口：族算分差 → 加本局杠分 → 落结算。四川血战会覆盖本方法。"""
        fan_delta, allocation, multipliers = self._settle_fan_delta(
            seat, breakdown, win_type, discard_seat, ctx
        )
        delta = [self.kong_accumulated[index] + fan_delta[index] for index in range(MAX_ROUNDS)]
        return self._finish(
            seat,
            win_type,
            tile,
            breakdown,
            delta,
            payer_allocation=allocation,
            multipliers=multipliers,
        )

    def _settle_draw(self) -> list[dict]:
        """牌墙取尽无人胡：有杠 → 荒庄（迁庄计局）；无杠 → 重发本局（不计数）。"""
        if not self.kong_happened:
            return self._restart_round()
        outcome = settle_draw(self.rule, self.dealer_seat, self.kong_accumulated)
        return self._finish(None, "none", None, None, outcome.delta)

    def _restart_round(self) -> list[dict]:
        """无杠重发：座位、庄家、局风、局号全部不变，重新洗牌发同一局（03 §3.6）。"""
        self.restarts += 1
        events = self.start_round()
        restart = {
            "type": "event.round_restarted",
            "data": {
                "round_no": self.round_no,
                "dealer_seat": self.dealer_seat,
                "round_wind": self.round_wind,
                "wall_count": self.remaining,
                "reason": "no_kong",
                "restarts": self.restarts,
            },
        }
        return [restart] + events

    def _finish(
        self,
        winner: int | None,
        win_type: str,
        tile: int | None,
        breakdown,
        delta: list[int],
        *,
        winners_list: list[dict] | None = None,
        payer_allocation: list[dict] | None = None,
        multipliers: dict | None = None,
        summary_text: str = "",
    ) -> list[dict]:
        self.phase = "settled"
        self.claim = None
        for index in range(MAX_ROUNDS):
            state = self.seat_state(index)
            state.round_score = delta[index]
            state.total_score += delta[index]

        fan_cap = getattr(self.rule, "fan_cap", None)
        winners_records = list(winners_list or [])
        if not winners_records and winner is not None:
            winners_records = [{"seat": winner, "win_type": win_type, "winning_tile": tile}]
        final_hands = final_hands_snapshot(
            [self.seat_state(index) for index in range(MAX_ROUNDS)], winners_records
        )
        self.result = SettledRound(
            round_no=self.round_no,
            dealer_seat=self.dealer_seat,
            winner_seat=winner,
            win_type=win_type,
            winning_tile=tile,
            pattern_id=breakdown.pattern_id if breakdown else None,
            fan_items=[line.to_dict() for line in breakdown.lines] if breakdown else [],
            fan_total=breakdown.fan_total if breakdown else 0,
            score_delta=delta,
            breakdown=breakdown.to_dict() if breakdown else None,
            round_wind=self.round_wind,
            fan_raw=breakdown.fan_raw if breakdown else 0,
            fan_cap=fan_cap,
            kong_delta=list(self.kong_accumulated),
            is_draw=winner is None,
            restarts=self.restarts,
            winners_list=list(winners_list or []),
            payer_allocation=list(payer_allocation or []),
            multipliers=dict(multipliers or {"self_draw": 1, "dealer": 1}),
            summary_text=summary_text or self._summary_text_of(breakdown),
            final_hands=final_hands,
        )
        return [
            {
                "type": "event.settled",
                "data": {
                    "round_no": self.round_no,
                    "dealer_seat": self.dealer_seat,
                    "round_wind": self.round_wind,
                    "winner_seat": winner,
                    "win_type": win_type,
                    "winning_tile": tile,
                    "pattern_id": self.result.pattern_id,
                    "fan_total": self.result.fan_total,
                    "fan_items": self.result.fan_items,
                    "score_delta": delta,
                    "summary": self.result.breakdown,
                    # S6 追加（只增字段不删字段，04 §12）
                    "winners": self.result.winners,
                    "fan_raw": self.result.fan_raw,
                    "fan_cap": self.result.fan_cap,
                    "kong_delta": self.result.kong_delta,
                    "is_draw": self.result.is_draw,
                    "restarts": self.result.restarts,
                    # S7 追加：包牌付款方分配与生效倍率（04 §9.4）
                    "payer_allocation": self.result.payer_allocation,
                    "multipliers": self.result.multipliers,
                    "summary_text": self.result.summary_text,
                },
            }
        ]

    def _summary_text_of(self, breakdown) -> str:
        if breakdown is None:
            return ""
        lines = breakdown.to_dict().get("lines") or []
        parts = [f"{line['name']} {line['fan']}" for line in lines if line.get("fan")]
        if not parts:
            return str(breakdown.pattern_name or "")
        return f"{breakdown.pattern_name}：" + " + ".join(parts)

    def next_dealer(self, settlement: SettledRound | None = None) -> int:
        """恒返回下家（03 §3.4）：每局换庄、第 n 局庄家 = 座位 n-1，不支持连庄。

        `settlement` 参数只为对齐 `RuleEngine` 协议，通用族不看输赢。
        """
        _ = settlement
        return (self.dealer_seat + 1) % MAX_ROUNDS


@runtime_checkable
class RuleEngine(Protocol):
    """引擎契约（03 §3.2）：四族共用同一组方法，房间层只认这套协议。

    族可以自由定义内部字段与方法，但下面这些必须存在——`families/registry.py`
    在导入期只做 capability 自检，方法级契约靠这个 Protocol（单测会 isinstance 校验）。
    """

    family_code: str
    rule: object
    seats: dict[int, SeatState]
    round_no: int
    dealer_seat: int
    round_wind: int
    turn: int
    phase: str
    result: SettledRound | None

    @property
    def tile_set(self) -> tuple[int, ...]: ...

    def start_round(self, dealer_seat: int | None = None, round_wind: int | None = None) -> list[dict]: ...

    def legal_actions(self, seat: int) -> dict: ...

    def apply_action(self, seat: int, action: dict) -> list[dict]: ...

    def timeout_claim(self) -> list[dict]: ...

    def tenpai_map(self, seat: int) -> dict[int, list[int]]: ...

    def settlement(self) -> dict | None: ...

    def next_dealer(self, settlement: SettledRound | None = None) -> int: ...

    def snapshot_options(self) -> dict: ...
