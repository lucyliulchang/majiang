"""生产侧包牌允许集核对（只读、不连库）。

跑在服务器上**已部署的**代码（默认 `/data/majiang/src`）上，直接调用
`game.families.baishi.fan.bao_pai_allowed_tile()`，逐条核对 07 §7.1（v1.13）口径：

| 牌型 | 点炮牌允许集 |
| --- | --- |
| 清一色 | 主花色的数牌 |
| 混一色 | 主花色的数牌（**字牌不算**） |
| 全文字 | 字牌 |
| 全幺 | 幺牌 = 1、9 数牌 **或** 字牌 |

用法（服务器上）：
    cd /data/majiang/src && /data/majiang/venv/bin/python /path/bao_check.py
退出码：0 = 全部通过，1 = 有不符项。输出末行为 JSON 摘要。
"""

from __future__ import annotations

import json
import os
import sys

SRC = os.environ.get("MJ_SRC", "/data/majiang/src")
sys.path.insert(0, SRC)

from game.families.baishi.fan import bao_pai_allowed_tile  # noqa: E402

# 牌张索引：0=1万 8=9万 9=1筒 18=1条 27=东 28=南 31=中 33=白
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


def main() -> int:
    failures = 0
    for name, tile, patterns, suit, want in CASES:
        got = bool(bao_pai_allowed_tile(tile, set(patterns), suit))
        ok = got == want
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    print(json.dumps({"cases": len(CASES), "all_pass": failures == 0}, ensure_ascii=False))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
