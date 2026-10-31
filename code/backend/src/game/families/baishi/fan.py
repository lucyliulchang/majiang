"""柏氏番种求值（07 §5 §6）。

本模块只产出**番种命中**（`FanHit`），不做封顶/折算：番值、互斥组、折算统统交给
`game/fan.py` 按模板 `fan_table` 处理（`fan_combine=sum_all` 即「同组取最高、其余全加」）。
这样改番值不用改代码，也保证「累计不乘积、不封顶」的口径只有一处实现。

判定顺序（07 §6.1）：先把副露摊进完整的 5 组结构，一手牌多解时**逐解求番取最高总分**。

互斥与抑制（07 §5）在这里落地：
- `quan` 组命中 ⇒ `structure` 组不计；
- `flush` 或 `quan` 组命中 ⇒ `que_men` 不计（双向抑制）；
- `三姊妹` 命中 ⇒ 其 3 副顺子不再计 一般高/姊妹花；
- `青龙`/`混龙` 命中 ⇒ 其组成顺子不再参与 连6/老少谱/一般高/姊妹花/三姊妹；
- `三暗刻`/`四暗刻` 自成 `anke` 组，只与彼此互斥，可与对对胡累加；
- 风刻（门风刻/圈风刻）不占任何组，可与任意番种累加，可叠加至 +2；
- 箭刻（中/发/白）每种一个刻子或杠各计 1 番，最多 3 番，不占任何组，可与任意番种累加；
- 十三幺不判独赢；七小对不判将牌（全文字七对例外，可叠独赢）；
- **13不靠 不判门清、独赢**（07 §6.3.4 v1.10 / R-6）：二者是牌型固有性质，不再重复计分；
  但局面番（天胡/地胡/杠上开花/海底捞月/抢杠胡）照常判定；
- 258赢（看 `win_tile`）与 断幺 / 一只幺（看 `all_tiles()`）是**牌型无关的全局番**，
  由 `global_fans()` 统一产出、在牌型 `calc_fan()` 出口追加（不逐个牌型挂），
  因此七对/13不靠/十三幺也照常判定（十三幺天然不成立）。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from game.hand import HandContext
from game.patterns.base import FanHit
from game.tiles import TILE_KINDS, is_honor, is_suit, rank_of, suit_of, tile_name

if TYPE_CHECKING:
    from game.families.baishi.config import RuleConfig

#: 07 §5 的 35 项番表（id → 名称、番值、互斥组、是否计数）
FAN_TABLE: tuple[tuple[str, str, int, str | None, bool], ...] = (
    ("ping_hu", "平胡", 1, "structure", False),
    ("men_qian", "门清", 1, "first", False),
    ("que_men", "缺门", 1, None, False),
    ("jiang_pai", "将牌", 1, None, False),
    ("du_ying", "独赢", 1, None, False),
    ("er_wu_ba_ying", "258赢", 1, None, False),
    ("qiang_gang_hu", "抢杠胡", 10, None, False),
    ("yi_ban_gao", "一般高", 1, None, True),
    ("zi_mei_hua", "姊妹花", 2, None, True),
    ("san_zi_mei", "三姊妹", 3, None, False),
    ("lao_shao_fu", "老少谱", 1, None, True),
    ("lian_liu", "连6", 1, None, True),
    ("hun_long", "混龙", 10, "long", False),
    ("qing_long", "青龙", 20, "long", False),
    ("dui_dui_hu", "对对胡", 10, "structure", False),
    ("san_an_ke", "三暗刻", 10, "anke", False),
    ("si_an_ke", "四暗刻", 20, "anke", False),
    ("qi_xiao_dui", "七小对", 20, "structure", False),
    ("shi_san_bu_kao", "13不靠", 10, "structure", False),
    ("shi_san_yao", "十三幺", 100, "quan", False),
    ("hun_yi_se", "混一色", 20, "flush", False),
    ("qing_yi_se", "清一色", 30, "flush", False),
    ("duan_yao", "断幺", 1, None, False),
    ("yi_zhi_yao", "一只幺", 1, None, False),
    ("quan_yao", "全幺", 50, "quan", False),
    ("quan_yao_qi_dui", "全幺七对", 60, "quan", False),
    ("quan_zi", "全文字", 100, "quan", False),
    ("quan_zi_qi_dui", "全文字七对", 120, "quan", False),
    ("tian_hu", "天胡", 100, "first", False),
    ("di_hu", "地胡", 50, "first", False),
    ("gang_shang_kai_hua", "杠上开花", 10, None, False),
    ("hai_di_lao_yue", "海底捞月", 100, None, False),
    ("men_feng_ke", "门风刻", 1, None, False),
    ("quan_feng_ke", "圈风刻", 1, None, False),
    ("jian_ke", "箭刻", 1, None, True),
)

FAN_VALUES: dict[str, int] = {fid: fan for fid, _name, fan, _grp, _cnt in FAN_TABLE}
FAN_NAMES: dict[str, str] = {fid: name for fid, name, _fan, _grp, _cnt in FAN_TABLE}

#: 番表的默认行（供 config 直接构造 `FanItem`）
FAN_DEFAULTS = FAN_TABLE

#: 一般高 / 姊妹花 / 老少谱 / 连6 / 箭刻 为计数型番种（同 id 按「组」各计一次）
STACKABLE_FANS = frozenset({"yi_ban_gao", "zi_mei_hua", "lao_shao_fu", "lian_liu", "jian_ke"})

#: 会抑制「缺门」的互斥组（07 §5 双向抑制）
QUE_MEN_SUPPRESSORS = frozenset({"flush", "quan"})

#: 包牌四选四的牌型（07 §7.1）
BAO_PAI_PATTERNS = ("qing_yi_se", "hun_yi_se", "quan_zi", "quan_yao")

#: 十三幺的 13 种幺九字牌
ORPHANS = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)
#: 十三不靠要求齐全的中发白
DRAGON_SET = (31, 32, 33)
#: 十三不靠同门内可选的牌组（147 / 258 / 369，0-based）
UNRELATED_GROUPS = ((0, 3, 6), (1, 4, 7), (2, 5, 8))


@dataclass
class SetInfo:
    """一组面子：顺子记起始牌，刻子记牌；杠按刻子计。"""

    kind: str  # "chow" | "pong"
    tile: int
    kong: bool = False
    concealed: bool = True
    from_meld: bool = False

    def tiles(self) -> list[int]:
        if self.kind == "chow":
            return [self.tile, self.tile + 1, self.tile + 2]
        return [self.tile] * (4 if self.kong else 3)


@dataclass
class HandShape:
    """一种拆解：将牌 + 4 组面子。"""

    pair: int
    sets: list[SetInfo] = field(default_factory=list)

    def all_tiles(self) -> list[int]:
        out = [self.pair, self.pair]
        for item in self.sets:
            out.extend(item.tiles())
        return out


# ---------------------------------------------------------------- 拆解


def _walk_sets(
    counts: list[int], sets_left: int, acc: list[tuple[str, int]], out: list[list[tuple[str, int]]], cap: int
) -> None:
    if len(out) >= cap:
        return
    if sets_left == 0:
        if not any(counts):
            out.append(list(acc))
        return
    first = -1
    for tile in range(TILE_KINDS):
        if counts[tile]:
            first = tile
            break
    if first < 0:
        return
    if counts[first] >= 3:
        counts[first] -= 3
        acc.append(("pong", first))
        _walk_sets(counts, sets_left - 1, acc, out, cap)
        acc.pop()
        counts[first] += 3
        if len(out) >= cap:
            return
    if is_suit(first) and first % 9 <= 6 and counts[first + 1] and counts[first + 2]:
        counts[first] -= 1
        counts[first + 1] -= 1
        counts[first + 2] -= 1
        acc.append(("chow", first))
        _walk_sets(counts, sets_left - 1, acc, out, cap)
        acc.pop()
        counts[first] += 1
        counts[first + 1] += 1
        counts[first + 2] += 1


def _meld_sets(ctx: HandContext) -> list[SetInfo]:
    result: list[SetInfo] = []
    for meld in ctx.melds:
        if meld.kind == "chow":
            result.append(SetInfo("chow", meld.tiles[0], from_meld=True, concealed=False))
        elif meld.kind == "pong":
            result.append(SetInfo("pong", meld.tiles[0], from_meld=True, concealed=False))
        elif meld.kind == "kong_exposed":
            result.append(SetInfo("pong", meld.tiles[0], kong=True, from_meld=True, concealed=False))
        elif meld.kind == "kong_added":
            result.append(SetInfo("pong", meld.tiles[0], kong=True, from_meld=True, concealed=False))
        elif meld.kind == "kong_hidden":
            result.append(SetInfo("pong", meld.tiles[0], kong=True, from_meld=True, concealed=True))
    return result


def shapes(ctx: HandContext, cap: int = 256) -> list[HandShape]:
    """4 组面子 + 1 将 的全部拆解（副露按已定型的面子摊入）。"""
    fixed = _meld_sets(ctx)
    if len(fixed) > 4:
        return []
    hand_sets = 4 - len(fixed)
    hand_counts = sum(ctx.counts)
    if hand_counts != hand_sets * 3 + 2:
        return []
    results: list[HandShape] = []
    work = list(ctx.counts)
    for pair in range(TILE_KINDS):
        if work[pair] < 2:
            continue
        work[pair] -= 2
        found: list[list[tuple[str, int]]] = []
        _walk_sets(work, hand_sets, [], found, cap)
        work[pair] += 2
        for sets in found:
            info = [SetInfo("chow", t) if kind == "chow" else SetInfo("pong", t) for kind, t in sets]
            results.append(HandShape(pair=pair, sets=info + list(fixed)))
        if len(results) >= cap:
            break
    return results


def is_seven_pairs(ctx: HandContext) -> bool:
    if ctx.melds or sum(ctx.counts) != 14:
        return False
    return all(count % 2 == 0 for count in ctx.counts)


def is_thirteen_orphans(ctx: HandContext) -> bool:
    if ctx.melds or sum(ctx.counts) != 14:
        return False
    if any(ctx.counts[tile] < 1 for tile in ORPHANS):
        return False
    if any(count and tile not in ORPHANS for tile, count in enumerate(ctx.counts)):
        return False
    return sum(1 for tile in ORPHANS if ctx.counts[tile] == 2) == 1


def unrelated_pair(ctx: HandContext) -> int | None:
    """13不靠的将牌（07 §6.3.4 宽松口径，I0 冻结的 7 步判定）。

    1. 14 张且无任何副露（门清；暗杠同样不允许）；
    2. 恰好一对将牌：`counts == 2` 只出现一次，且没有 3 张以上的牌；
    3. 中发白必含：各 ≥1（其中一种恰为将牌时自然为 2 张）；
    4. 风牌每种 ≤1（扣将后；成对时只能是将牌）；
    5. 数牌每门 0–3 张、同门全部落在同一组（147/258/369）、不得重复同一张；
    6. 全部牌都被上述规则覆盖（总数守恒，无多余牌）；
    7. 返回该将牌。
    """
    if ctx.melds or sum(ctx.counts) != 14:
        return None
    for pair in range(TILE_KINDS):
        if ctx.counts[pair] < 2:
            continue
        # 将牌不受「同门同组 / 不重复」约束，先扣除 2 张，再看剩余 12 张
        rest = list(ctx.counts)
        rest[pair] -= 2
        if any(count > 1 for count in rest):
            continue  # 剩余牌里不允许再出现对子/三张（恰好一对将）
        if any(ctx.counts[tile] < 1 for tile in DRAGON_SET):
            continue  # 中发白必含（将牌可为其中一种）
        if any(rest[tile] > 1 for tile in (27, 28, 29, 30)):
            continue  # 风牌每种最多 1 张，成对时只能是将牌
        ok = True
        for suit in range(3):
            base = suit * 9
            ranks = tuple(rank for rank in range(9) if rest[base + rank])
            if any(rest[base + rank] > 1 for rank in ranks):
                ok = False  # 同门不得重复同一张牌
                break
            if ranks and not any(set(ranks) <= set(group) for group in UNRELATED_GROUPS):
                ok = False  # 同门必须落在 147 / 258 / 369 同一组内（0–3 张，可为该组的子集）
                break
        if ok and sum(rest) == 12:  # 全覆盖：14 张 = 将 2 + 中发白 3 + 风 0–4 + 数牌 0–9
            return pair
    return None


# ---------------------------------------------------------------- 局面番


def _suit_profile(ctx: HandContext) -> tuple[set[int], bool]:
    suits: set[int] = set()
    has_honor = False
    for tile, count in enumerate(ctx.counts):
        if count <= 0:
            continue
        if is_honor(tile):
            has_honor = True
        else:
            suits.add(suit_of(tile))
    for tile in ctx.meld_tiles:
        if is_honor(tile):
            has_honor = True
        else:
            suits.add(suit_of(tile))
    return suits, has_honor


def flush_fan(ctx: HandContext) -> str | None:
    """混一色 / 清一色（`flush` 组）；纯字牌走 `quan` 组，不在此返回。"""
    suits, has_honor = _suit_profile(ctx)
    if len(suits) != 1:
        return None
    return "hun_yi_se" if has_honor else "qing_yi_se"


def is_all_terminals(ctx: HandContext) -> bool:
    """全幺：全部 1/9/字牌，且至少含一张 1 或 9（07 §6.4.3）。"""
    tiles = ctx.all_tiles()
    if not tiles:
        return False
    numbered = False
    for tile in tiles:
        if is_honor(tile):
            continue
        rank = rank_of(tile)
        if rank not in (0, 8):
            return False
        numbered = True
    return numbered


def is_all_honors(ctx: HandContext) -> bool:
    tiles = ctx.all_tiles()
    return bool(tiles) and all(is_honor(tile) for tile in tiles)


def is_all_simples(ctx: HandContext) -> bool:
    """断幺（07 §6.4.8）：手牌 + **全部副露**都不含 1/9 数牌、也不含任何字牌。"""
    tiles = ctx.all_tiles()
    if not tiles:
        return False
    return all(is_suit(tile) and rank_of(tile) not in (0, 8) for tile in tiles)


# ---------------------------------------------------------------- 赢张类 / 全局番


def er_wu_ba_ying_hit(ctx: HandContext) -> list[FanHit]:
    """258赢（07 §6.11）：**最后赢张**为数牌 2/5/8；与将牌无关，一手只计 1 次。"""
    tile = ctx.win_tile
    if tile is None or not is_suit(tile):
        return []
    return [FanHit("er_wu_ba_ying")] if rank_of(tile) in (1, 4, 7) else []


def duan_yao_hit(ctx: HandContext) -> list[FanHit]:
    """断幺（07 §6.4.8）：整手牌（含副露）全为 2–8 数牌。"""
    return [FanHit("duan_yao")] if is_all_simples(ctx) else []


def count_yao_tiles(ctx: HandContext) -> int:
    """整手牌（手牌 + 全部副露摊平）里「幺牌」的**张数**（07 §6.4.9）。

    幺牌 = 数牌 **1、9**（`rank_of` ∈ {0, 8}）与**全部字牌**（东南西北中发白）。
    按**张数**计、不按「种」计：`1 万 + 东` 是 2 张幺（2 种），不成立。

    逐张统计而非按「组」归类：幺牌除将(2)/刻(3)/杠(4) 外还会出现在
    **123 / 789 顺子的端张**（`fan.py:154` 的顺子起点条件 `first % 9 <= 6`
    允许 123 与 789），只统计成组的牌会漏判、导致该番永不命中。
    """
    return sum(1 for tile in ctx.all_tiles() if is_honor(tile) or rank_of(tile) in (0, 8))


def yi_zhi_yao_hit(ctx: HandContext) -> list[FanHit]:
    """一只幺（07 §6.4.9）：胡牌后的整手 14 张牌（含副露摊平）里恰好 1 张幺牌。

    与断幺天然互斥（断幺 = 0 张幺牌）；与 `quan` 组天然互斥（七对/十三幺/全幺/
    全文字必含 ≥2 张幺牌，13不靠 必含中发白 3 张）；不占任何互斥组，一手只计一次。
    """
    return [FanHit("yi_zhi_yao")] if count_yao_tiles(ctx) == 1 else []


def global_fans(ctx: HandContext) -> list[FanHit]:
    """与牌型结构无关的全局番（258赢 / 断幺 / 一只幺）。

    由各牌型 `calc_fan()` 出口统一追加（`baishi/patterns.py:_with_global_fans`），
    所以七对、13不靠、十三幺也照常判定；十三幺的赢张必为幺九字牌，天然不成立。
    """
    return [*er_wu_ba_ying_hit(ctx), *duan_yao_hit(ctx), *yi_zhi_yao_hit(ctx)]


def situational_hits(ctx: HandContext) -> list[FanHit]:
    """只看局面的番：门清、天胡/地胡、杠上开花、海底捞月、抢杠胡。"""
    hits: list[FanHit] = []
    if ctx.is_heavenly:
        hits.append(FanHit("tian_hu"))
    elif ctx.is_earthly:
        hits.append(FanHit("di_hu"))
    elif not ctx.has_exposed_meld:
        hits.append(FanHit("men_qian"))
    if ctx.is_after_kong:
        hits.append(FanHit("gang_shang_kai_hua"))
    # 海底捞月：牌墙最后一张恰为 1 筒且摸者自摸胡（07 §6.5.2）
    if ctx.is_last_tile and ctx.is_self_draw and ctx.win_tile == 9:
        hits.append(FanHit("hai_di_lao_yue"))
    if ctx.is_robbing_kong:
        hits.append(FanHit("qiang_gang_hu"))
    return hits


def wind_ke_hits(sets: list[SetInfo], seat_wind: int, round_wind: int) -> list[FanHit]:
    """门风刻 / 圈风刻（07 §6.9）：各计一次、可叠加；将牌不算刻子。"""
    pongs = {item.tile for item in sets if item.kind == "pong"}
    hits: list[FanHit] = []
    if 27 + seat_wind in pongs:
        hits.append(FanHit("men_feng_ke"))
    if 27 + round_wind in pongs:
        hits.append(FanHit("quan_feng_ke"))
    return hits


def jian_ke_hits(sets: list[SetInfo]) -> list[FanHit]:
    """箭刻（07 §6.10）：中/发/白 每种一个刻子或杠各 1 番，最多 3 番；将牌不算刻子。"""
    pongs = {item.tile for item in sets if item.kind == "pong"}
    count = sum(1 for tile in DRAGON_SET if tile in pongs)
    return [FanHit("jian_ke", count)] if count else []


def jiang_pai_hit(pair: int) -> list[FanHit]:
    """将牌：2/5/8/1/9 或任意字牌（0-based rank ∈ {0,1,4,7,8}）（07 §6.7）。"""
    if is_honor(pair) or rank_of(pair) in (0, 1, 4, 7, 8):
        return [FanHit("jiang_pai")]
    return []


def wait_forms(shape: HandShape, win_tile: int | None) -> set[str]:
    """胡张形态：两面 / 嵌张 / 单吊 / 单边 / 对倒。"""
    if win_tile is None:
        return {"other"}
    forms: set[str] = set()
    base = win_tile - win_tile % 9 if is_suit(win_tile) else 0
    for item in shape.sets:
        if item.from_meld:
            continue
        if item.kind == "pong":
            if item.tile == win_tile and not item.kong:
                forms.add("pengpeng")
            continue
        if not (item.tile <= win_tile <= item.tile + 2):
            continue
        partners = [item.tile, item.tile + 1, item.tile + 2]
        partners.remove(win_tile)
        low, high = partners
        if low == win_tile - 1 and high == win_tile + 1:
            forms.add("kan")
        elif high == win_tile - 1:
            # 两张在低位等高位：1-2 等 3 是单边，其余是两面
            forms.add("penchan" if low == base else "ryanmen")
        elif low == win_tile + 1:
            forms.add("penchan" if high == base + 8 else "ryanmen")
    if shape.pair == win_tile:
        forms.add("single")
    return forms or {"other"}


def du_ying_hit(forms: set[str]) -> list[FanHit]:
    """独赢 = 嵌张 / 单吊 / 单边；两面不算（07 §6.8）。"""
    if "ryanmen" in forms:
        return []
    if forms & {"kan", "single", "penchan"}:
        return [FanHit("du_ying")]
    return []


# ---------------------------------------------------------------- 顺子类


def _long_of(chows: list[int]) -> tuple[str, list[int]] | None:
    """青龙 / 混龙（07 §6.2）：123+456+789 三副齐。"""
    for suit in range(3):
        base = suit * 9
        if all(base + offset in chows for offset in (0, 3, 6)):
            return "qing_long", [base, base + 3, base + 6]
    for low in [tile for tile in chows if tile % 9 == 0]:
        for mid in [tile for tile in chows if tile % 9 == 3]:
            for high in [tile for tile in chows if tile % 9 == 6]:
                if len({low // 9, mid // 9, high // 9}) >= 2:
                    return "hun_long", [low, mid, high]
    return None


def chow_fans(chows: list[int]) -> list[FanHit]:
    """顺子类番种（一般高/姊妹花/三姊妹/老少谱/连6 + 龙）。

    `chows` 为顺子起始牌列表；龙命中时其组成顺子先被剔除（07 §6.2 龙上位规则）。
    """
    pool = list(chows)
    hits: list[FanHit] = []
    long_found = _long_of(pool)
    if long_found is not None:
        fan_id, used = long_found
        hits.append(FanHit(fan_id))
        for tile in used:
            pool.remove(tile)

    # 三姊妹：同花色同数序三副，固定 3 番，替代这 3 对的姊妹花/一般高
    by_key: dict[tuple[int, int], list[int]] = defaultdict(list)
    for tile in pool:
        by_key[(tile // 9, tile % 9)].append(tile)
    triple_keys = [key for key, items in by_key.items() if len(items) >= 3]
    if triple_keys:
        hits.append(FanHit("san_zi_mei"))
        for key in triple_keys[:1]:
            for _ in range(3):
                pool.remove(key[0] * 9 + key[1])

    # 一般高（异花色 1 番/对）/ 姊妹花（同花色 2 番/对）：同名数序两两成对
    by_rank: dict[int, list[int]] = defaultdict(list)
    for tile in pool:
        by_rank[tile % 9].append(tile)
    gao = 0
    hua = 0
    for _rank, items in by_rank.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if items[i] // 9 == items[j] // 9:
                    hua += 1
                else:
                    gao += 1
    if gao:
        hits.append(FanHit("yi_ban_gao", gao))
    if hua:
        hits.append(FanHit("zi_mei_hua", hua))

    # 老少谱：同花色 123 + 789 各一副
    lao = 0
    for suit in range(3):
        base = suit * 9
        lao += min(pool.count(base), pool.count(base + 6))
    if lao:
        hits.append(FanHit("lao_shao_fu", lao))

    # 连6：同花色 123456 / 234567 / 456789
    lian = 0
    for suit in range(3):
        base = suit * 9
        for low, high in ((0, 3), (1, 4), (3, 6)):
            if base + low in pool and base + high in pool:
                lian += 1
    if lian:
        hits.append(FanHit("lian_liu", lian))
    return hits


# ---------------------------------------------------------------- 结构类


def _concealed_pongs(shape: HandShape) -> int:
    return sum(1 for item in shape.sets if item.kind == "pong" and item.concealed)


def _anke_hits(shape: HandShape) -> list[FanHit]:
    count = _concealed_pongs(shape)
    if count >= 4:
        return [FanHit("si_an_ke")]
    if count == 3:
        return [FanHit("san_an_ke")]
    return []


def shape_fans(ctx: HandContext, shape: HandShape) -> list[FanHit]:
    """一组拆解的全部番种（不含 `anke` 取高，交给互斥组处理）。"""
    chows = [item.tile for item in shape.sets if item.kind == "chow"]
    all_chow = all(item.kind == "chow" for item in shape.sets)
    all_pong = all(item.kind == "pong" for item in shape.sets)
    forms = wait_forms(shape, ctx.win_tile)

    structure: list[FanHit] = []
    if all_pong:
        structure.append(FanHit("dui_dui_hu"))
    if (
        all_chow
        and not any(item.kong for item in shape.sets)
        and forms == {"ryanmen"}
        and is_suit(shape.pair)
        and rank_of(shape.pair) in (2, 3, 5, 6)
    ):
        structure.append(FanHit("ping_hu"))

    quan: list[FanHit] = []
    if is_all_honors(ctx) and all_pong:
        quan.append(FanHit("quan_zi"))
    elif is_all_terminals(ctx):
        quan.append(FanHit("quan_yao"))

    flush = flush_fan(ctx)
    hits: list[FanHit] = []
    # 全文字/全幺 与 structure 组互斥（07 §5）
    hits.extend([] if quan else structure)
    if flush:
        hits.append(FanHit(flush))
    hits.extend(quan)
    hits.extend(_anke_hits(shape))
    hits.extend(chow_fans(chows))
    hits.extend(jiang_pai_hit(shape.pair))
    hits.extend(du_ying_hit(forms))
    hits.extend(wind_ke_hits(shape.sets, ctx.seat_wind, ctx.round_wind))
    hits.extend(jian_ke_hits(shape.sets))
    hits.extend(situational_hits(ctx))
    if not (flush or quan):
        suits, _honors = _suit_profile(ctx)
        if len(suits) <= 2:
            hits.append(FanHit("que_men"))
    return hits


def seven_pairs_fans(ctx: HandContext) -> list[FanHit]:
    """七小对 / 全幺七对 / 全文字七对（07 §5 §6.4）。七对不判将牌。"""
    hits: list[FanHit] = []
    if is_all_honors(ctx):
        hits.append(FanHit("quan_zi_qi_dui"))
        # 07 §6.4.6：全文字七对可叠门清与独赢（单吊）
        hits.append(FanHit("du_ying"))
    elif is_all_terminals(ctx):
        hits.append(FanHit("quan_yao_qi_dui"))
    else:
        hits.append(FanHit("qi_xiao_dui"))
    flush = flush_fan(ctx)
    if flush:
        hits.append(FanHit(flush))
    hits.extend(situational_hits(ctx))
    if not (flush or is_all_honors(ctx) or is_all_terminals(ctx)):
        suits, _honors = _suit_profile(ctx)
        if len(suits) <= 2:
            hits.append(FanHit("que_men"))
    return hits


def thirteen_orphans_fans(ctx: HandContext) -> list[FanHit]:
    """十三幺 100 + 幺将 1 + 门清 1 = 102；不判独赢（07 §6.3.6）。"""
    hits: list[FanHit] = [FanHit("shi_san_yao"), FanHit("jiang_pai")]
    if not ctx.has_exposed_meld:
        hits.append(FanHit("men_qian"))
    if ctx.is_after_kong:
        hits.append(FanHit("gang_shang_kai_hua"))
    if ctx.is_last_tile and ctx.is_self_draw and ctx.win_tile == 9:
        hits.append(FanHit("hai_di_lao_yue"))
    if ctx.is_robbing_kong:
        hits.append(FanHit("qiang_gang_hu"))
    if ctx.is_heavenly:
        hits.append(FanHit("tian_hu"))
    return hits


def thirteen_unrelated_fans(ctx: HandContext, pair: int) -> list[FanHit]:
    """13不靠：只与 structure 组互斥，将牌等照常累加（07 §6.3.4）。

    v1.10 起（R-6）**不再计门清、独赢**：13不靠 的「必门清 + 必单吊」是牌型固有性质，
    再各计 1 番属重复计分。13不靠 **仍判**：将牌、缺门、混一色/清一色。
    注意区分——「不许有副露」是**牌型成立条件**（`unrelated_pair()` 仍要求 `ctx.melds` 为空），
    「不计门清番」只是**判番口径**，两者互不影响。
    """
    hits: list[FanHit] = [FanHit("shi_san_bu_kao")]
    hits.extend(jiang_pai_hit(pair))
    flush = flush_fan(ctx)
    if flush:
        hits.append(FanHit(flush))
    # ⚠️ 不得整体删除 `situational_hits(ctx)`：它同时产出天胡 / 地胡 / 杠上开花 /
    # 海底捞月 / 抢杠胡 5 个番种；这里只把 13不靠 不再计的 `men_qian` 过滤掉。
    hits.extend(hit for hit in situational_hits(ctx) if hit.id != "men_qian")
    if not flush:
        suits, _honors = _suit_profile(ctx)
        if len(suits) <= 2:
            hits.append(FanHit("que_men"))
    return hits


# ---------------------------------------------------------------- 最高分解


def _fan_value(rule: "RuleConfig", fan_id: str) -> int:
    finder = getattr(rule, "fan_of", None)
    if callable(finder):
        item = finder(fan_id)
        if item is not None:
            return int(getattr(item, "fan", 0) or 0)
    return FAN_VALUES.get(fan_id, 0)


def _total(rule: "RuleConfig", hits: list[FanHit]) -> int:
    return sum(_fan_value(rule, hit.id) * max(1, hit.count) for hit in hits)


def best_shape_fans(ctx: HandContext, rule: "RuleConfig") -> list[FanHit]:
    """逐解求番取最高总分（07 §6.1）。"""
    best: list[FanHit] = []
    best_score = -1
    for shape in shapes(ctx):
        hits = shape_fans(ctx, shape)
        score = _total(rule, hits)
        if score > best_score:
            best_score = score
            best = hits
    return best


# ---------------------------------------------------------------- 包牌


def bao_pai_allowed_tile(tile: int, pattern_ids: set[str], main_suit: int | None) -> bool:
    """点炮牌是否落在该牌型的允许集内（07 §7.1）。"""
    if "quan_zi" in pattern_ids:
        if is_honor(tile):
            return True
    if "quan_yao" in pattern_ids:
        if is_honor(tile) or rank_of(tile) in (0, 8):
            return True
    if "qing_yi_se" in pattern_ids and main_suit is not None:
        if is_suit(tile) and suit_of(tile) == main_suit:
            return True
    if "hun_yi_se" in pattern_ids and main_suit is not None:
        if is_honor(tile) or (is_suit(tile) and suit_of(tile) == main_suit):
            return True
    return False


def main_suit_of(ctx: HandContext) -> int | None:
    suits, _honors = _suit_profile(ctx)
    if len(suits) == 1:
        return next(iter(suits))
    return None


__all__ = [
    "BAO_PAI_PATTERNS",
    "FAN_DEFAULTS",
    "FAN_NAMES",
    "FAN_TABLE",
    "FAN_VALUES",
    "HandShape",
    "ORPHANS",
    "QUE_MEN_SUPPRESSORS",
    "STACKABLE_FANS",
    "SetInfo",
    "bao_pai_allowed_tile",
    "best_shape_fans",
    "chow_fans",
    "count_yao_tiles",
    "du_ying_hit",
    "duan_yao_hit",
    "er_wu_ba_ying_hit",
    "flush_fan",
    "global_fans",
    "is_all_honors",
    "is_all_simples",
    "is_all_terminals",
    "is_seven_pairs",
    "is_thirteen_orphans",
    "jian_ke_hits",
    "jiang_pai_hit",
    "main_suit_of",
    "seven_pairs_fans",
    "shape_fans",
    "shapes",
    "situational_hits",
    "thirteen_orphans_fans",
    "thirteen_unrelated_fans",
    "unrelated_pair",
    "wait_forms",
    "wind_ke_hits",
    "yi_zhi_yao_hit",
]
