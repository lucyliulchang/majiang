"""柏氏规则引擎（07 §3 §7 §8 §9）。

与通用骨架的差异全部落在这里：
1. **累计求番**：`fan_combine=sum_all` + 不封顶（`fan_total = fan_raw`），
   由 `game/fan.py` 按模板番表求值，本模块不重复实现；
2. **倍数结算**（07 §3.2）：`U = 底分 × 番合计`，付款方应付 `U × m_自摸 × m_庄家`，
   自摸 ×2、庄家胡全体 ×2、闲家胡庄家份 ×2，三者叠加；
3. **包牌**（07 §7）：点炮 + ≥3 组明牌 + 命中 清一色/混一色/全文字/全幺 +
   点炮牌属于该牌型 ⇒ 点炮者独付三家应付款之和；赢家实收不变，`score_delta` 守恒；
4. **杠分**（07 §8）：明杠 1 / 暗杠 2 / 补杠 1，三家各付，不占番、不乘倍数；
5. **抢杠**（07 §6.5.4）：只有明杠开抢杠窗口，三家各付、不乘自摸倍数、不触发包牌；
6. **牌尾补牌与海底**：补牌走牌墙尾部（骨架 `_begin_turn(from_tail=True)`），
   海底捞月的判定在 `baishi/fan.py`（最后一张恰为 1 筒且摸者自摸胡，100 番）。
"""

from __future__ import annotations

from game.engine import GameEngine, MAX_ROUNDS
from game.fan import ScoreBreakdown
from game.hand import HandContext
from game.tiles import TILE_SET_136

from game.families.baishi import fan as baishi_fan

FAMILY = "baishi"


class BaishiEngine(GameEngine):
    family_code = "baishi"
    tile_set_code = TILE_SET_136

    # ------------------------------------------------------------------ 杠分
    def _kong_delta(self, seat: int, kind: str, from_seat: int | None) -> list[int]:
        """柏氏杠分：明杠 1、暗杠 2、补杠 1，**三家各付**、不乘倍数（07 §8）。"""
        points = self.rule.kong_points(kind)
        delta = [0, 0, 0, 0]
        if points <= 0:
            return delta
        pay_mode = str(getattr(self.rule.kong_score, "pay_mode", "all") or "all")
        if pay_mode == "discarder" and kind == "exposed" and from_seat is not None:
            if from_seat == seat:
                return delta
            delta[from_seat] -= points
            delta[seat] += points
            return delta
        for payer in range(MAX_ROUNDS):
            if payer == seat:
                continue
            delta[payer] -= points
            delta[seat] += points
        return delta

    # ------------------------------------------------------------------ 结算
    def _dealer_multiplier_of(self, winner_seat: int, payer_seat: int) -> int:
        rule = self.rule
        dealer = getattr(rule, "dealer_rule", None)
        win_multiplier = int(getattr(dealer, "win_multiplier", 1) or 1)
        pay_multiplier = int(getattr(dealer, "pay_multiplier", 1) or 1)
        if winner_seat == self.dealer_seat:
            return win_multiplier
        if payer_seat == self.dealer_seat:
            return pay_multiplier
        return 1

    def _bao_pai_of(
        self,
        ctx: HandContext | None,
        breakdown: ScoreBreakdown,
        win_type: str,
        discard_seat: int | None,
        tile: int | None,
    ) -> tuple[bool, list[str]]:
        """包牌四条（07 §7.1），返回 `(是否包牌, 命中的牌型)`。"""
        options = getattr(self.rule, "bao_pai", None)
        if options is None or not getattr(options, "enabled", False):
            return False, []
        if ctx is None or win_type != "discard" or discard_seat is None or tile is None:
            return False, []
        if len(ctx.exposed_melds) < int(getattr(options, "min_exposed_melds", 3)):
            return False, []
        lines = {line.id for line in breakdown.lines}
        allowed = set(getattr(options, "patterns", ()) or ())
        matched = sorted(lines & allowed)
        if not matched:
            return False, []
        main_suit = baishi_fan.main_suit_of(ctx)
        if not baishi_fan.bao_pai_allowed_tile(tile, set(matched), main_suit):
            return False, []
        return True, matched

    def _settle_fan_delta(
        self,
        winner_seat: int,
        breakdown: ScoreBreakdown,
        win_type: str,
        discard_seat: int | None,
        ctx: HandContext | None = None,
        tile: int | None = None,
    ) -> tuple[list[int], list[dict], dict]:
        """U = 底分 × 番合计；倍数按 07 §3.2 叠加；包牌时改为点炮者独付三家之和。"""
        unit = int(getattr(breakdown, "score", 0) or 0)
        self_draw_multiplier = int(getattr(self.rule, "self_draw_multiplier", 1) or 1)
        # 抢杠胡「不走点炮、不乘自摸倍数」（07 §12 Q1）
        m_self_draw = self_draw_multiplier if win_type == "self_draw" else 1

        dues: dict[int, int] = {}
        for payer in range(MAX_ROUNDS):
            if payer == winner_seat:
                continue
            dues[payer] = unit * m_self_draw * self._dealer_multiplier_of(winner_seat, payer)

        winner_is_dealer = winner_seat == self.dealer_seat
        multipliers = {
            "self_draw": m_self_draw,
            "dealer": (
                int(getattr(self.rule.dealer_rule, "win_multiplier", 1))
                if winner_is_dealer
                else int(getattr(self.rule.dealer_rule, "pay_multiplier", 1))
            ),
        }

        win_tile = tile if tile is not None else (ctx.win_tile if ctx is not None else None)
        bao, matched = self._bao_pai_of(ctx, breakdown, win_type, discard_seat, win_tile)
        delta = [0, 0, 0, 0]
        if bao and discard_seat is not None:
            total = sum(dues.values())
            delta[discard_seat] -= total
            delta[winner_seat] += total
            covered = [seat for seat in dues if seat != discard_seat]
            allocation = [
                {
                    "winner_seat": winner_seat,
                    "reason": "bao_pai",
                    "bao_pai_seat": discard_seat,
                    "patterns": matched,
                    "covered": covered,
                    "payers": [{"seat": discard_seat, "amount": -total}],
                    "amount": total,
                }
            ]
            return delta, allocation, multipliers

        for payer, amount in dues.items():
            delta[payer] -= amount
            delta[winner_seat] += amount
        return delta, [], multipliers

    def _finish_win(
        self,
        seat: int,
        win_type: str,
        tile: int | None,
        breakdown: ScoreBreakdown,
        discard_seat: int | None,
        ctx: HandContext | None = None,
    ) -> list[dict]:
        fan_delta, allocation, multipliers = self._settle_fan_delta(
            seat, breakdown, win_type, discard_seat, ctx, tile
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


def create_engine(rule, seats, **kwargs) -> BaishiEngine:
    from game.families.baishi.config import RuleConfig
    from game.families.registry import coerce_config

    return BaishiEngine(coerce_config(rule, RuleConfig), seats, **kwargs)


__all__ = ["BaishiEngine", "create_engine"]
