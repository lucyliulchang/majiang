"""生产侧规则核对（只读、不连库）：v1.1.0 四项新增/修订番种。

跑在服务器上的已部署代码（/data/majiang/src），直接构造 HandContext 求番，
对应 07 §13-09（13不靠）、13-32（258赢）、13-33（连6）、13-34（断幺）。
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("MYSQL_SKIP_CONNECT", "1")
sys.path.insert(0, "/data/majiang/src")

from game.fan import best_win  # noqa: E402
from game.families.baishi.config import RuleConfig  # noqa: E402
from game.families.baishi.fan import FAN_TABLE  # noqa: E402
from game.hand import HandContext, Meld  # noqa: E402
from game.patterns import collect_wins  # noqa: E402
from game.tiles import counts_from_tiles  # noqa: E402

SUITS = {"m": 0, "p": 1, "s": 2}
RULE = RuleConfig()


def parse_hand(text: str) -> list[int]:
    tiles: list[int] = []
    pending: list[int] = []
    for char in text:
        if char.isdigit():
            pending.append(int(char))
            continue
        if char in " ,":
            pending.clear()
            continue
        if char in SUITS:
            tiles.extend(SUITS[char] * 9 + number - 1 for number in pending)
            pending.clear()
        elif char == "z":
            tiles.extend(27 + number - 1 for number in pending)
            pending.clear()
    return tiles


def evaluate(text: str, win_tile=None, melds=None):
    ctx = HandContext(
        counts=counts_from_tiles(parse_hand(text)),
        melds=list(melds or []),
        win_tile=win_tile,
        is_self_draw=False,
        seat_wind=0,
        round_wind=0,
    )
    breakdown = best_win(collect_wins(ctx, RULE), RULE)
    if breakdown is None:  # 不成胡（反例用例）
        return {}, 0
    return {line.id: line.fan * line.count for line in breakdown.lines}, breakdown.fan_total


results = {"fan_table_size": len(FAN_TABLE), "cases": []}


def case(name: str, text: str, win_tile, expect_ids: list[str], forbidden: list[str] | None = None, melds=None):
    ids, total = evaluate(text, win_tile, melds)
    ok = all(ids.get(key, 0) > 0 for key in expect_ids) and all(key not in ids for key in (forbidden or []))
    results["cases"].append(
        {
            "case": name,
            "hand": text,
            "win_tile": win_tile,
            "fan_items": ids,
            "fan_total": total,
            "pass": ok,
        }
    )
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ids} total={total}")
    return ok


# 07-13-32 258赢（赢张 2/5/8）
case("13-32 258赢·赢2条", "234m567m345p234s55s", 19, ["er_wu_ba_ying"])
case("13-32 258赢·赢8条", "234m567m345p678s55s", 25, ["er_wu_ba_ying"])
case("13-32 258赢+断幺·赢8万", "678m234p567s234s55s", 7, ["er_wu_ba_ying", "duan_yao"])
case("13-32 反例·赢3万", "234m567m345p234s55s", 2, [], ["er_wu_ba_ying"])

# 07-13-33 连6（同花色 6 连，1 番/组）
case("13-33 连6·单组", "123456m234p678s55s", 5, ["lian_liu"])
case("13-33 连6·两组", "123456m234567p55s", 5, ["lian_liu"])

# 07-13-34 断幺（含副露）
case("13-34 断幺·全2-8", "234m567m345p678s55s", 4, ["duan_yao"])
case("13-34 反例·含1万", "123m567m345p678s55s", 4, [], ["duan_yao"])
case(
    "13-34 断幺·副露吃456万",
    "567m345p678s55s",
    4,
    ["duan_yao"],
    melds=[Meld(kind="chow", tiles=[3, 4, 5], from_seat=1)],
)
case(
    "13-34 反例·副露吃123万",
    "567m345p678s55s",
    4,
    [],
    ["duan_yao"],
    melds=[Meld(kind="chow", tiles=[0, 1, 2], from_seat=1)],
)

# 07-13-09 十三不靠（宽松口径：可含风牌、允许缺门、将可为字牌）
# v1.10 起（R-6）不再计门清 / 独赢 → 期望里剔除，并用 forbidden 锁定
case(
    "13-09 13不靠·标准",
    "147m258p58s22s1z5z6z7z",
    18,
    ["shi_san_bu_kao", "jiang_pai"],
    forbidden=["men_qian", "du_ying"],
)
case(
    "13-09 13不靠·含风牌",
    "1z1z2z3z5z6z7z1m4m7m2s5s8s3p",
    27,
    ["shi_san_bu_kao", "jiang_pai"],
    forbidden=["men_qian", "du_ying"],
)
case(
    "13-09 13不靠·缺门",
    "1z1z2z3z4z5z6z7z1m4m7m2s5s8s",
    27,
    ["shi_san_bu_kao", "que_men"],
    forbidden=["men_qian", "du_ying"],
)
# v1.12：任何牌不得超过 2 张 → 中×3（中将 + 第 3 张中）不成立
case(
    "13-09 13不靠·三张同牌不成立",
    "5z5z5z6z7z1m4m7m2p5p8p3s6s9s",
    31,
    [],
    forbidden=["shi_san_bu_kao"],
)
# v1.13：数牌将必须与同门散牌同组 → 1/7 条 + 8 条 8 条 不成立（实测反馈用例）
case(
    "13-09 13不靠·将牌跨组不成立",
    "17m1p17s88s1234567z",
    33,
    [],
    forbidden=["shi_san_bu_kao"],
)
# v1.13：将牌所在门无散牌 → 视为只取将牌所属组，成立
case(
    "13-09 13不靠·独立门将牌成立",
    "55m147s258p1z2z3z5z6z7z",
    4,
    ["shi_san_bu_kao", "jiang_pai"],
    forbidden=["men_qian", "du_ying"],
)

results["all_pass"] = all(item["pass"] for item in results["cases"])
print(json.dumps({"fan_table_size": results["fan_table_size"], "all_pass": results["all_pass"]}, ensure_ascii=False))
if len(sys.argv) > 1:
    with open(sys.argv[1], "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
