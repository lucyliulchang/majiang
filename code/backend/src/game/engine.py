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
from game.fan import best_win
from game.hand import HandContext, Meld
from game.patterns import collect_wins, is_winning, winning_tiles
from game.scoring import kong_delta, settle_draw, settle_rob_kong, settle_win
from game.tiles import (
    TILE_SET_136,
    empty_counts,
    new_wall,
    tile_kinds_of,
    tile_name,
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
    """一局结算（03 §3.2 `RoundSettlement` 的单赢家形态；通用族 winners 长度恒为 0/1）。"""

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

    @property
    def winners(self) -> list[dict]:
        """统一结构：单赢家长度 1，荒庄为空（03 §3.2）。"""
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
                "multipliers": {"self_draw": 1, "dealer": 1},
                "score_from_fan": self.breakdown.get("score", 0) if self.breakdown else 0,
                "breakdown": self.breakdown,
            }
        ]


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
        )

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
            if is_winning(self._ctx(seat, win_tile=self.last_draw), self.rule):
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
            "payer_allocation": [],
            "kong_delta": list(settled.kong_delta),
            "summary": self._summary_text(settled),
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

        state.counts[tile] -= 1
        state.discards.append(tile)
        self.last_discard = tile
        self.last_discard_seat = seat
        self.after_kong = False
        self.last_draw = None

        events = [{"type": "event.discarded", "data": {"seat": seat, "tile": tile}}]
        window = self._build_claim_window(tile, seat, reason="discard")
        if window is None:
            events.extend(self._begin_turn((seat + 1) % 4))
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

    def _build_claim_window(self, tile: int, from_seat: int, reason: str = "discard") -> ClaimWindow | None:
        options: dict[int, list[dict]] = {}
        for seat in _order_after(from_seat):
            state = self.seat_state(seat)
            actions: list[dict] = []
            if reason == "discard":
                if is_winning(
                    self._ctx(seat, win_tile=tile, is_self_draw=False, extra_tile=tile), self.rule
                ):
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
                if is_winning(
                    self._ctx(
                        seat,
                        win_tile=tile,
                        is_self_draw=False,
                        is_robbing_kong=True,
                        extra_tile=tile,
                    ),
                    self.rule,
                ):
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
            if window.reason == "rob_kong":
                assert window.kong_seat is not None
                events = self._apply_added_kong(window.kong_seat, window.tile)
                events.extend(self._begin_turn(window.kong_seat, from_tail=True))
                return events
            return self._begin_turn((window.from_seat + 1) % 4)

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
        state.melds.append(Meld(kind="pong", tiles=[tile, tile, tile], from_seat=window.from_seat))
        self._take_from_river(window.from_seat, tile)
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
            Meld(kind="chow", tiles=chow_tiles(window.tile, partners), from_seat=window.from_seat)
        )
        self._take_from_river(window.from_seat, window.tile)
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

    def _do_exposed_kong(self, seat: int, window: ClaimWindow) -> list[dict]:
        state = self.seat_state(seat)
        tile = window.tile
        state.counts[tile] -= 3
        state.melds.append(
            Meld(kind="kong_exposed", tiles=[tile] * 4, from_seat=window.from_seat)
        )
        self._take_from_river(window.from_seat, tile)
        self.kong_happened = True
        events = [
            {
                "type": "event.kongged",
                "data": {"seat": seat, "kind": "exposed", "tile": tile, "from_seat": window.from_seat},
            }
        ]
        events.extend(self._award_kong(seat, "exposed", window.from_seat))
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
                    kind="kong_added", tiles=[tile] * 4, from_seat=meld.from_seat
                )
                break
        self.kong_happened = True
        events = [{"type": "event.kongged", "data": {"seat": seat, "kind": "added", "tile": tile}}]
        events.extend(self._award_kong(seat, "added", None))
        return events

    def _award_kong(self, seat: int, kind: str, from_seat: int | None) -> list[dict]:
        self.kong_happened = True
        delta = kong_delta(self.rule, seat, kind, from_seat)
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
        wins = collect_wins(ctx, self.rule)
        breakdown = best_win(wins, self.rule)
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡")
        outcome = settle_win(
            self.rule,
            winner_seat=seat,
            breakdown=breakdown,
            is_self_draw=True,
            discard_seat=None,
            kong_accumulated=self.kong_accumulated,
        )
        return self._finish(seat, "self_draw", self.last_draw, breakdown, outcome.delta)

    def _settle_discard_hu(self, seat: int, from_seat: int, tile: int) -> list[dict]:
        ctx = self._ctx(seat, win_tile=tile, is_self_draw=False, extra_tile=tile)
        wins = collect_wins(ctx, self.rule)
        breakdown = best_win(wins, self.rule)
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡")
        outcome = settle_win(
            self.rule,
            winner_seat=seat,
            breakdown=breakdown,
            is_self_draw=False,
            discard_seat=from_seat,
            kong_accumulated=self.kong_accumulated,
        )
        return self._finish(seat, "discard", tile, breakdown, outcome.delta)

    def _settle_rob_kong(self, seat: int, kong_seat: int, tile: int) -> list[dict]:
        ctx = self._ctx(
            seat, win_tile=tile, is_self_draw=False, is_robbing_kong=True, extra_tile=tile
        )
        wins = collect_wins(ctx, self.rule)
        breakdown = best_win(wins, self.rule)
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡")
        outcome = settle_rob_kong(
            self.rule,
            winner_seat=seat,
            breakdown=breakdown,
            kong_seat=kong_seat,
            kong_accumulated=self.kong_accumulated,
        )
        return self._finish(seat, "discard", tile, breakdown, outcome.delta)

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
        self, winner: int | None, win_type: str, tile: int | None, breakdown, delta: list[int]
    ) -> list[dict]:
        self.phase = "settled"
        self.claim = None
        for index in range(4):
            state = self.seat_state(index)
            state.round_score = delta[index]
            state.total_score += delta[index]

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
            fan_cap=self.rule.fan_cap,
            kong_delta=list(self.kong_accumulated),
            is_draw=winner is None,
            restarts=self.restarts,
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
                },
            }
        ]

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
