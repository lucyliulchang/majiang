"""对局状态机。

状态：waiting → discard（该谁出牌）→ claim（碰杠胡询问窗口）→ discard … → settled
所有合法性校验都在这里完成，前端提交的只是"意图"。
"""

from dataclasses import dataclass, field

from game.claims import ClaimWindow, chow_options, chow_tiles
from game.fan import best_win
from game.hand import HandContext, Meld
from game.patterns import collect_wins, is_winning, winning_tiles
from game.scoring import kong_delta, settle_draw, settle_rob_kong, settle_win
from game.tiles import empty_counts, new_wall, tile_name
from schemas.rule import RuleConfig


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


def _order_after(seat: int) -> list[int]:
    return [(seat + step) % 4 for step in range(1, 4)]


class GameEngine:
    def __init__(
        self,
        rule: RuleConfig,
        seats: list[SeatState],
        round_no: int = 1,
        dealer_seat: int = 0,
        round_wind: int = 0,
    ):
        self.rule = rule
        self.seats: dict[int, SeatState] = {item.seat: item for item in seats}
        self.round_no = round_no
        self.dealer_seat = dealer_seat
        self.round_wind = round_wind

        self.wall: list[int] = []
        self.front = 0
        self.back = -1
        self.turn = dealer_seat
        self.phase = "waiting"
        self.last_draw: int | None = None
        self.after_kong = False
        self.last_discard: int | None = None
        self.last_discard_seat: int | None = None
        self.claim: ClaimWindow | None = None
        self.kong_accumulated: list[int] = [0, 0, 0, 0]
        self.result: SettledRound | None = None

    # ------------------------------------------------------------------ 基础
    @property
    def remaining(self) -> int:
        return max(0, self.back - self.front + 1)

    def seat_state(self, seat: int) -> SeatState:
        state = self.seats.get(seat)
        if state is None:
            raise EngineError("NO_SEAT", "该座位没有玩家")
        return state

    def seat_wind(self, seat: int) -> int:
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
    def start_round(self) -> list[dict]:
        self.wall = new_wall()
        self.front = 0
        self.back = len(self.wall) - 1
        self.phase = "dealing"
        self.result = None
        self.claim = None
        self.kong_accumulated = [0, 0, 0, 0]
        self.last_discard = None
        self.last_discard_seat = None
        self.after_kong = False

        for state in self.seats.values():
            state.counts = empty_counts()
            state.melds = []
            state.discards = []
            state.round_score = 0

        for _ in range(13):
            for seat in [(self.dealer_seat + step) % 4 for step in range(4)]:
                tile = self._draw_front()
                if tile is None:
                    break
                self.seat_state(seat).counts[tile] += 1

        dealt = self._draw_front()
        if dealt is not None:
            self.seat_state(self.dealer_seat).counts[dealt] += 1
        self.last_draw = dealt
        self.turn = self.dealer_seat
        self.phase = "discard"

        return [
            {
                "type": "event.round_started",
                "data": {
                    "round_no": self.round_no,
                    "dealer_seat": self.dealer_seat,
                    "round_wind": self.round_wind,
                    "wall_count": self.remaining,
                },
            },
            self._turn_event(),
        ]

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
        events = [{"type": "event.kongged", "data": {"seat": seat, "kind": "added", "tile": tile}}]
        events.extend(self._award_kong(seat, "added", None))
        return events

    def _award_kong(self, seat: int, kind: str, from_seat: int | None) -> list[dict]:
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
        outcome = settle_draw(self.rule, self.dealer_seat, self.kong_accumulated)
        return self._finish(None, "none", None, None, outcome.delta)

    def _finish(self, winner: int | None, win_type: str, tile: int | None, breakdown, delta: list[int]) -> list[dict]:
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
        )
        return [
            {
                "type": "event.settled",
                "data": {
                    "round_no": self.round_no,
                    "dealer_seat": self.dealer_seat,
                    "winner_seat": winner,
                    "win_type": win_type,
                    "winning_tile": tile,
                    "pattern_id": self.result.pattern_id,
                    "fan_total": self.result.fan_total,
                    "fan_items": self.result.fan_items,
                    "score_delta": delta,
                    "summary": self.result.breakdown,
                },
            }
        ]

    def next_dealer(self) -> int:
        """庄家是否连庄。"""
        if self.result is None:
            return self.dealer_seat
        if self.result.winner_seat == self.dealer_seat and self.rule.dealer_continue_on_win:
            return self.dealer_seat
        if self.result.winner_seat is None and self.rule.dealer_continue_on_draw:
            return self.dealer_seat
        return (self.dealer_seat + 1) % 4
