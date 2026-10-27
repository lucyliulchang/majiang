"""结算：把番数折算成四家的分数增减。

铁律：杠分一律先判 rule.kong_score.enabled 再取值，
      关闭时杠牌照常进行，但一分不给。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from game.fan import ScoreBreakdown

if TYPE_CHECKING:
    from game.families.generic.config import RuleConfig

SEATS = 4


def _zeros() -> list[int]:
    return [0] * SEATS


def kong_delta(
    rule: RuleConfig, seat: int, kind: str, from_seat: int | None = None
) -> list[int]:
    """杠分。返回四家增减（下标即座位）。

    - 明杠：放杠的那位付 exposed 分
    - 暗杠 / 补杠：其余三家各付 hidden / added 分
    """
    points = rule.kong_points(kind)
    if points <= 0:
        return _zeros()
    delta = _zeros()
    if kind == "exposed":
        if from_seat is None or from_seat == seat:
            return _zeros()
        delta[from_seat] -= points
        delta[seat] += points
        return delta
    payers = [s for s in range(SEATS) if s != seat]
    for payer in payers:
        delta[payer] -= points
        delta[seat] += points
    return delta


@dataclass
class RoundOutcome:
    winner_seat: int | None
    win_type: str  # "self_draw" | "discard" | "none"
    discount_seat: int | None
    score: int
    breakdown: ScoreBreakdown | None
    delta: list[int]


def settle_win(
    rule: RuleConfig,
    winner_seat: int,
    breakdown: ScoreBreakdown,
    is_self_draw: bool,
    discard_seat: int | None,
    kong_accumulated: list[int] | None = None,
) -> RoundOutcome:
    score = breakdown.score
    delta = list(kong_accumulated) if kong_accumulated else _zeros()

    if is_self_draw:
        for seat in range(SEATS):
            if seat == winner_seat:
                continue
            delta[seat] -= score
            delta[winner_seat] += score
        win_type = "self_draw"
    else:
        payer = discard_seat if discard_seat is not None else -1
        if rule.discard_pay_mode == "all":
            for seat in range(SEATS):
                if seat == winner_seat:
                    continue
                delta[seat] -= score
                delta[winner_seat] += score
        else:
            if 0 <= payer < SEATS:
                delta[payer] -= score
                delta[winner_seat] += score
            else:
                delta[winner_seat] += score
        win_type = "discard"

    return RoundOutcome(
        winner_seat=winner_seat,
        win_type=win_type,
        discount_seat=discard_seat,
        score=score,
        breakdown=breakdown,
        delta=delta,
    )


def settle_draw(rule: RuleConfig, dealer_seat: int, kong_accumulated: list[int] | None = None) -> RoundOutcome:
    """荒庄：默认不输不赢；开了荒庄罚分则其余三家付给庄家。"""
    delta = list(kong_accumulated) if kong_accumulated else _zeros()
    if rule.draw_penalty.enabled:
        points = rule.draw_penalty.value or 0
        if points > 0:
            for seat in range(SEATS):
                if seat == dealer_seat:
                    continue
                delta[seat] -= points
                delta[dealer_seat] += points
    return RoundOutcome(
        winner_seat=None,
        win_type="none",
        discount_seat=None,
        score=0,
        breakdown=None,
        delta=delta,
    )


def settle_rob_kong(
    rule: RuleConfig,
    winner_seat: int,
    breakdown: ScoreBreakdown,
    kong_seat: int,
    kong_accumulated: list[int] | None = None,
) -> RoundOutcome:
    """抢杠胡：被抢的那位当放炮者付分。"""
    return settle_win(
        rule=rule,
        winner_seat=winner_seat,
        breakdown=breakdown,
        is_self_draw=False,
        discard_seat=kong_seat,
        kong_accumulated=kong_accumulated,
    )
