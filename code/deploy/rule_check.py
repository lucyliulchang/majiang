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
case("13-09 13不靠·标准", "147m258p369s5z6z7z9m9m", 26, ["shi_san_bu_kao", "du_ying", "jiang_pai"])
case("13-09 13不靠·含风牌", "1z1z2z3z5z6z7z1m4m7m2s5s8s3p", 27, ["shi_san_bu_kao", "men_qian"])
case("13-09 13不靠·缺门", "1z1z2z3z4z5z6z7z1m4m7m2s5s8s", 27, ["shi_san_bu_kao", "que_men"])

results["all_pass"] = all(item["pass"] for item in results["cases"])
print(json.dumps({"fan_table_size": results["fan_table_size"], "all_pass": results["all_pass"]}, ensure_ascii=False))
if len(sys.argv) > 1:
    with open(sys.argv[1], "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
