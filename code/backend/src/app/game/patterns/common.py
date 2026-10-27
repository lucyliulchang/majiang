"""多个牌型共用的番种计算片段。"""

from app.game.hand import HandContext
from app.game.patterns.base import FanHit
from app.game.tiles import is_honor, is_suit, suit_of
from app.schemas.rule import RuleConfig


def suit_fan_hits(ctx: HandContext) -> list[FanHit]:
    """清一色 / 混一色 / 字一色。三者互斥，交给 exclusive_group 去重也能兜住。"""
    tiles = ctx.all_tiles()
    suits = {suit_of(t) for t in tiles if is_suit(t)}
    has_honor = any(is_honor(t) for t in tiles)
    if not suits:
        return [FanHit("zi_yi_se")] if has_honor else []
    if len(suits) == 1:
        return [FanHit("hun_yi_se" if has_honor else "qing_yi_se")]
    return []


def situational_fan_hits(ctx: HandContext, rule: RuleConfig) -> list[FanHit]:
    """与牌面结构无关、只看局面的番：自摸、门清、杠、海底、杠上开花、抢杠胡。"""
    hits: list[FanHit] = []
    if ctx.is_self_draw:
        hits.append(FanHit("zi_mo"))
    if not ctx.has_exposed_meld:
        hits.append(FanHit("men_qian"))
    kong_count = sum(1 for meld in ctx.melds if meld.is_kong)
    if kong_count and rule.kong_score.enabled:
        # 杠本身另有杠分；这里只是"每杠 +1 番"的番种，关掉杠分时不叠加
        hits.append(FanHit("kong", kong_count))
    if ctx.is_last_tile:
        hits.append(FanHit("hai_di"))
    if ctx.is_after_kong:
        hits.append(FanHit("gang_shang_hua"))
    if ctx.is_robbing_kong:
        hits.append(FanHit("qiang_gang_hu"))
    return hits
