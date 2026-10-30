"""四川血战到底引擎（03 §6）：108 张、禁吃、缺一门、多赢家。

与通用骨架的差异全部落在这里，骨架只多出几个可覆盖的钩子（`_out_seats` /
`_next_active` / `_settle_fan_delta` / `_rob_kong_kinds`），路由层不需要认识族名。

血战口径：
1. 一家胡牌即**退出**（`out_seats`），其余继续摸打，直到 3 人胡或牌墙耗尽；
2. 已退出的玩家不再参与后续赔分（付款方 = 仍在场的其余玩家）；
3. 一张弃牌上可以多家同时胡（一炮多响），按打牌者下家起的顺序依次结算；
4. 对外事件类型不变：中途胡牌用增量的 `event.hu_recorded` 广播，
   真正的收口仍是 `event.settled`（`winners` 长度 1–3）。
"""

from __future__ import annotations

from game.claims import ClaimWindow
from game.engine import EngineError, GameEngine, MAX_ROUNDS
from game.fan import ScoreBreakdown
from game.tiles import TILE_SET_108

FAMILY = "sichuan"


class SichuanEngine(GameEngine):
    family_code = "sichuan"
    tile_set_code = TILE_SET_108

    def __init__(self, rule, seats, **kwargs):
        super().__init__(rule, seats, **kwargs)
        self.out_seats: set[int] = set()
        self.winners: list[dict] = []
        self.score_accum: list[int] = [0, 0, 0, 0]
        self.payer_allocation: list[dict] = []
        self._first_breakdown: ScoreBreakdown | None = None
        self._first_win: tuple[int, str, int | None] | None = None

    # ------------------------------------------------------------------ 复位
    def start_round(self, dealer_seat: int | None = None, round_wind: int | None = None) -> list[dict]:
        self.out_seats = set()
        self.winners = []
        self.score_accum = [0, 0, 0, 0]
        self.payer_allocation = []
        self._first_breakdown = None
        self._first_win = None
        return super().start_round(dealer_seat, round_wind)

    # ------------------------------------------------------------------ 钩子
    def _out_seats(self) -> set[int]:
        return self.out_seats

    def _next_active(self, seat: int) -> int:
        """下一个仍在场的座位（血战：胡牌者退出，跳过他的位子）。"""
        for step in range(1, MAX_ROUNDS + 1):
            candidate = (seat + step) % MAX_ROUNDS
            if candidate not in self.out_seats:
                return candidate
        return seat

    def _active_seats(self) -> list[int]:
        return [seat for seat in range(MAX_ROUNDS) if seat not in self.out_seats]

    def _settle_fan_delta(
        self,
        winner_seat: int,
        breakdown: ScoreBreakdown,
        win_type: str,
        discard_seat: int | None,
        ctx=None,
    ) -> tuple[list[int], list[dict], dict]:
        """血战付款：自摸/抢杠由在场三家各付，点炮由点炮者独付；已胡者不再付。"""
        score = int(getattr(breakdown, "score", 0) or 0)
        delta = [0, 0, 0, 0]
        if win_type == "self_draw" or win_type == "rob_kong":
            payers = [seat for seat in self._active_seats() if seat != winner_seat]
        elif discard_seat is not None and discard_seat != winner_seat:
            payers = [discard_seat]
        else:
            payers = []
        for payer in payers:
            delta[payer] -= score
            delta[winner_seat] += score
        return delta, [], {"self_draw": 1, "dealer": 1}

    def _win_record(self, seat: int, win_type: str, tile: int | None, breakdown: ScoreBreakdown) -> dict:
        return {
            "seat": seat,
            "win_type": win_type,
            "winning_tile": tile,
            "pattern_id": breakdown.pattern_id,
            "fan_items": [line.to_dict() for line in breakdown.lines],
            "fan_raw": breakdown.fan_raw,
            "fan_cap": getattr(self.rule, "fan_cap", None),
            "fan_total": breakdown.fan_total,
            "multipliers": {"self_draw": 1, "dealer": 1},
            "score_from_fan": breakdown.score,
            "breakdown": breakdown.to_dict(),
        }

    # ------------------------------------------------------------------ 胡牌
    def _record_win(
        self,
        seat: int,
        win_type: str,
        tile: int | None,
        breakdown: ScoreBreakdown,
        discard_seat: int | None,
    ) -> list[dict]:
        """记一家胡牌：结算给分、标记退出；未到终局则继续，到了就收口。"""
        fan_delta, allocation, _multipliers = self._settle_fan_delta(
            seat, breakdown, win_type, discard_seat
        )
        for index in range(MAX_ROUNDS):
            self.score_accum[index] += fan_delta[index]
        self.payer_allocation.extend(allocation)
        self.winners.append(self._win_record(seat, win_type, tile, breakdown))
        if self._first_breakdown is None:
            self._first_breakdown = breakdown
            self._first_win = (seat, win_type, tile)
        self.out_seats.add(seat)
        self.claim = None

        events = [
            {
                "type": "event.hu_recorded",
                "data": {
                    "seat": seat,
                    "win_type": win_type,
                    "winning_tile": tile,
                    "pattern_id": breakdown.pattern_id,
                    "fan_raw": breakdown.fan_raw,
                    "fan_total": breakdown.fan_total,
                    "score_delta": fan_delta,
                    "winners_count": len(self.winners),
                    "remaining_players": len(self._active_seats()),
                },
            }
        ]
        if self._round_over():
            return events + self._finish_multi()
        return events + self._continue_after_win(seat, win_type, discard_seat)

    def _round_over(self) -> bool:
        """3 人胡 → 结束；只剩 1 人（其他人全胡）→ 结束。"""
        return len(self._active_seats()) <= 1 or len(self.winners) >= 3

    def _continue_after_win(self, seat: int, win_type: str, discard_seat: int | None) -> list[dict]:
        if self.remaining <= 0:
            return self._finish_multi()
        if win_type == "self_draw":
            return self._begin_turn(self._next_active(seat))
        origin = discard_seat if discard_seat is not None else seat
        return self._begin_turn(self._next_active(origin))

    def _finish_multi(self) -> list[dict]:
        if not self.winners:
            return self._settle_draw()
        delta = [
            self.kong_accumulated[index] + self.score_accum[index] for index in range(MAX_ROUNDS)
        ]
        first_seat, first_type, first_tile = self._first_win or (
            self.winners[0]["seat"],
            self.winners[0]["win_type"],
            self.winners[0]["winning_tile"],
        )
        return self._finish(
            first_seat,
            first_type,
            first_tile,
            self._first_breakdown,
            delta,
            winners_list=list(self.winners),
            payer_allocation=list(self.payer_allocation),
            multipliers={"self_draw": 1, "dealer": 1},
        )

    def _do_self_draw_hu(self, seat: int) -> list[dict]:
        breakdown = self.evaluate_win(
            self._ctx(seat, win_tile=self.last_draw, is_self_draw=True)
        )
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡（四川要缺一门）")
        return self._record_win(seat, "self_draw", self.last_draw, breakdown, None)

    def _settle_discard_hu(self, seat: int, from_seat: int, tile: int) -> list[dict]:
        breakdown = self.evaluate_win(
            self._ctx(seat, win_tile=tile, is_self_draw=False, extra_tile=tile)
        )
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡（四川要缺一门）")
        return self._record_win(seat, "discard", tile, breakdown, from_seat)

    def _settle_rob_kong(self, seat: int, kong_seat: int, tile: int) -> list[dict]:
        breakdown = self.evaluate_win(
            self._ctx(
                seat, win_tile=tile, is_self_draw=False, is_robbing_kong=True, extra_tile=tile
            )
        )
        if breakdown is None:
            raise EngineError("NOT_WIN", "这副牌还没胡（四川要缺一门）")
        return self._record_win(seat, "rob_kong", tile, breakdown, kong_seat)

    # ------------------------------------------------------------------ 一炮多响
    def _hu_ends_round(self) -> bool:
        """血战到底：一家胡牌后本局继续（胡家出局、其余照打），因此不能"胡即收口"短路。

        短路会把仍在犹豫的座位按终态 pass 收掉，而这里的吃碰杠在本局继续时是有意义的。
        """
        return False

    def _resolve_claim(self) -> list[dict]:
        window = self.claim
        if window is None:
            return []
        self.claim = None

        if window.reason == "discard":
            hu_seats = [
                seat
                for seat in window._seat_order()
                if (window.responses.get(seat) or {}).get("action") == "hu"
            ]
            if len(hu_seats) > 1:
                return self._multi_hu(hu_seats, window)

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
        raise EngineError("BAD_ACTION", "四川不能吃牌" if kind == "chow" else "无法识别的动作")

    def _multi_hu(self, hu_seats: list[int], window: ClaimWindow) -> list[dict]:
        """一炮多响：同一张弃牌上多家同时胡，按座位序依次结算。"""
        tile = window.tile
        events: list[dict] = []
        self._take_from_river(window.from_seat, tile)
        for seat in hu_seats:
            breakdown = self.evaluate_win(
                self._ctx(seat, win_tile=tile, is_self_draw=False, extra_tile=tile)
            )
            if breakdown is None:
                continue
            events.extend(self._record_win(seat, "discard", tile, breakdown, window.from_seat))
            if self.phase == "settled":
                return events
        if self.phase == "settled":
            return events
        if self.remaining <= 0:
            return events + self._finish_multi()
        return events + self._begin_turn(self._next_active(window.from_seat))

    # ------------------------------------------------------------------ 荒庄
    def _settle_draw(self) -> list[dict]:
        """牌墙取尽：有赢家 → 按赢家收口（不是荒庄）；否则沿用骨架的荒庄二分。"""
        if self.winners:
            return self._finish_multi()
        return super()._settle_draw()

    # ------------------------------------------------------------------ 查询
    def legal_actions(self, seat: int) -> dict:
        if seat in self.out_seats:
            return {"actions": []}
        return super().legal_actions(seat)

    def apply_action(self, seat: int, action: dict) -> list[dict]:
        if seat in self.out_seats and self.phase != "settled":
            raise EngineError("SEAT_OUT", "你已经胡牌，本局不再行动")
        return super().apply_action(seat, action)


def create_engine(rule, seats, **kwargs) -> SichuanEngine:
    from game.families.registry import coerce_config
    from game.families.sichuan.config import RuleConfig

    return SichuanEngine(coerce_config(rule, RuleConfig), seats, **kwargs)


__all__ = ["SichuanEngine", "create_engine"]
