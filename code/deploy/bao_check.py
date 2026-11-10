"""生产侧包牌允许集核对（只读、不连库）。

跑在服务器上**已部署的**代码（默认 `/data/majiang/src`）上，直接调用
`game.families.baishi.fan` 的两个判定，逐条核对 07 §7.1（v1.16）口径。

A. 点炮牌允许集（`bao_pai_allowed_tile`）

| 牌型 | 点炮牌允许集 |
| --- | --- |
| 清一色 | 主花色的数牌 |
| 混一色 | 主花色的数牌（**字牌不算**） |
| 全文字 | 字牌 |
| 全幺 | 幺牌 = 1、9 数牌 **或** 字牌 |

B. 明牌须已亮出特征牌（`bao_pai_exposed_ok`，v1.16 新增第 5 条）

| 牌型 | 明牌里必须至少有一张 |
| --- | --- |
| 清一色 / 混一色 | 主花色数牌（明牌全是字牌 ⇒ **不包**） |
| 全文字 | 字牌（恒成立） |
| 全幺 | 幺牌（恒成立） |

用法（服务器上）：
    cd /data/majiang/src && sudo /data/majiang/venv/bin/python /path/bao_check.py
退出码：0 = 全部通过，1 = 有不符项。输出末行为 JSON 摘要。
"""

from __future__ import annotations

import json
import os
import sys

SRC = os.environ.get("MJ_SRC", "/data/majiang/src")
sys.path.insert(0, SRC)

from game.families.baishi.fan import (  # noqa: E402
    bao_pai_allowed_tile,
    bao_pai_exposed_ok,
)

# 牌张索引：0=1万 8=9万 9=1筒 18=1条 27=东 31=中 33=白
CASES: list[tuple[str, int, set[str], int | None, bool]] = [
    ("清一色 + 主花色数牌(1万)", 0, {"qing_yi_se"}, 0, True),
    ("清一色 + 字牌(东)", 27, {"qing_yi_se"}, 0, False),
    ("清一色 + 他门数牌(1筒)", 9, {"qing_yi_se"}, 0, False),
    ("混一色 + 主花色数牌(1万)", 0, {"hun_yi_se"}, 0, True),
    ("混一色 + 字牌(东) · v1.13 修复点", 27, {"hun_yi_se"}, 0, False),
    ("混一色 + 他门数牌(1筒)", 9, {"hun_yi_se"}, 0, False),
    ("全文字 + 字牌(中)", 31, {"quan_zi"}, None, True),
    ("全文字 + 数牌(1万)", 0, {"quan_zi"}, None, False),
    ("全幺 + 字牌(东)", 27, {"quan_yao"}, 0, True),
    ("全幺 + 1/9 数牌(9万)", 8, {"quan_yao"}, 0, True),
    ("全幺 + 2~8 数牌(2万)", 1, {"quan_yao"}, 0, False),
    ("混一色 + 全幺 + 字牌(东)", 27, {"hun_yi_se", "quan_yao"}, 0, True),
    ("混一色 + 全幺 + 主花色数牌(9万)", 8, {"hun_yi_se", "quan_yao"}, 0, True),
]

# 明牌（副露摊平后的牌编码列表）→ 是否已亮出该牌型的特征牌
EXPOSED_CASES: list[tuple[str, list[int], set[str], int | None, bool]] = [
    ("混一色 · 明牌全字牌(西发中) · v1.16 修复点", [29, 29, 29, 32, 32, 32, 31, 31, 31], {"hun_yi_se"}, 1, False),
    ("混一色 · 明牌含主花色数牌(456筒)", [12, 13, 14, 29, 29, 29, 32, 32, 32], {"hun_yi_se"}, 1, True),
    ("混一色 · 明牌含他门数牌(456万)", [3, 4, 5, 29, 29, 29, 32, 32, 32], {"hun_yi_se"}, 1, False),
    ("清一色 · 明牌含主花色数牌(123万)", [0, 1, 2, 3, 3, 3, 6, 6, 6], {"qing_yi_se"}, 0, True),
    ("全文字 · 明牌全字牌", [29, 29, 29, 31, 31, 31, 32, 32, 32], {"quan_zi"}, None, True),
    ("全幺 · 明牌含幺牌(111万)", [0, 0, 0, 9, 9, 9, 18, 18, 18], {"quan_yao"}, 0, True),
]


def main() -> int:
    failures = 0
    for name, tile, patterns, suit, want in CASES:
        got = bool(bao_pai_allowed_tile(tile, set(patterns), suit))
        ok = got == want
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] A 点炮牌 {name}: got={got} want={want}")
    for name, exposed, patterns, suit, want in EXPOSED_CASES:
        got = bool(bao_pai_exposed_ok(exposed, set(patterns), suit))
        ok = got == want
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] B 明牌 {name}: got={got} want={want}")
    total = len(CASES) + len(EXPOSED_CASES)
    print(
        json.dumps(
            {"cases": total, "allowed_tile_cases": len(CASES), "exposed_cases": len(EXPOSED_CASES), "all_pass": failures == 0},
            ensure_ascii=False,
        )
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
