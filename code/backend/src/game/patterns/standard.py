"""标准胡：4 面子 + 1 将。递归拆解 + 回溯，多解取最大番。"""

from game.hand import HandContext
from game.patterns.base import FanHit, register_pattern
from game.patterns.common import situational_fan_hits, suit_fan_hits
from game.tiles import TILE_KINDS, is_suit
from schemas.rule import RuleConfig


def _walk(
    counts: list[int],
    sets_left: int,
    acc: list[tuple[str, int]],
    out: list[tuple[tuple[str, int], ...]],
    stop_at: int,
) -> None:
    if len(out) >= stop_at:
        return
    if sets_left == 0:
        if not any(counts):
            out.append(tuple(acc))
        return

    first = -1
    for tile in range(TILE_KINDS):
        if counts[tile]:
            first = tile
            break
    if first < 0:
        return

    # 先试刻子，再试顺子，保证拆法覆盖完整
    if counts[first] >= 3:
        counts[first] -= 3
        acc.append(("pong", first))
        _walk(counts, sets_left - 1, acc, out, stop_at)
        acc.pop()
        counts[first] += 3
        if len(out) >= stop_at:
            return

    if is_suit(first) and first % 9 <= 6 and counts[first + 1] and counts[first + 2]:
        counts[first] -= 1
        counts[first + 1] -= 1
        counts[first + 2] -= 1
        acc.append(("chow", first))
        _walk(counts, sets_left - 1, acc, out, stop_at)
        acc.pop()
        counts[first] += 1
        counts[first + 1] += 1
        counts[first + 2] += 1


def decompositions(
    counts: list[int], stop_at: int = 256
) -> list[tuple[int, tuple[tuple[str, int], ...]]]:
    """返回全部（将牌, 面子构成）拆法。"""
    total = sum(counts)
    if total < 2 or total % 3 != 2:
        return []
    sets_needed = (total - 2) // 3
    results: list[tuple[int, tuple[tuple[str, int], ...]]] = []
    work = list(counts)
    for pair in range(TILE_KINDS):
        if work[pair] < 2:
            continue
        work[pair] -= 2
        found: list[tuple[tuple[str, int], ...]] = []
        _walk(work, sets_needed, [], found, stop_at)
        work[pair] += 2
        for sets in found:
            results.append((pair, sets))
        if len(results) >= stop_at:
            break
    return results


def _structure_fans(ctx: HandContext, pair: int, sets: tuple[tuple[str, int], ...]) -> list[FanHit]:
    kinds: list[tuple[str, int]] = list(sets)
    for meld in ctx.melds:
        if meld.is_kong:
            kinds.append(("pong", meld.tiles[0]))
        elif meld.kind == "pong":
            kinds.append(("pong", meld.tiles[0]))
        else:
            kinds.append(("chow", meld.tiles[0]))

    hits: list[FanHit] = []
    if all(kind == "chow" for kind, _ in kinds):
        hits.append(FanHit("ping_hu"))
    if all(kind == "pong" for kind, _ in kinds):
        hits.append(FanHit("peng_peng_hu"))

    chows = [start for kind, start in kinds if kind == "chow"]
    if len(chows) != len(set(chows)):
        hits.append(FanHit("yi_ban_gao"))
    chow_set = set(chows)
    for start in chows:
        rank = start % 9
        if all(rank + suit * 9 in chow_set for suit in range(3)):
            hits.append(FanHit("san_se_tong_shun"))
            break

    pongs = {start for kind, start in kinds if kind == "pong"}
    if 27 + ctx.seat_wind in pongs:
        hits.append(FanHit("men_feng"))
    if 27 + ctx.round_wind in pongs:
        hits.append(FanHit("quan_feng"))
    if any(tile in pongs for tile in (31, 32, 33)):
        hits.append(FanHit("jian_ke"))
    _ = pair
    return hits


class StandardPattern:
    id = "standard"
    name = "标准胡"

    def match(self, ctx: HandContext) -> bool:
        if sum(ctx.counts) % 3 != 2:
            return False
        return bool(decompositions(ctx.counts, stop_at=1))

    def calc_fan(self, ctx: HandContext, rule: RuleConfig) -> list[FanHit]:
        options = decompositions(ctx.counts)
        if not options:
            return []
        hits: list[FanHit] = []
        hits.extend(suit_fan_hits(ctx))
        hits.extend(situational_fan_hits(ctx, rule))
        # 取面子结构番最多的那种拆法
        best: list[FanHit] = []
        best_score = -1
        for pair, sets in options:
            candidate = _structure_fans(ctx, pair, sets)
            score = sum(rule.fan_of(hit.id).fan if rule.fan_of(hit.id) else 0 for hit in candidate)
            if score > best_score:
                best_score = score
                best = candidate
        hits.extend(best)
        return hits


register_pattern(StandardPattern)
