"""预置模板逐字段对比：旧 config（S6 之前）↔ 新 config（families/generic/presets.py）。

基线来源：`tests/fixtures/legacy_presets.json`，由 S6 之前的 `schemas/rule.py`
（git `afb26dc`）跑 `RuleConfig(...).model_dump()` 生成并冻结，因此对比不是"自己比自己"。

对比口径（03 §4.5、S6 验收清单）：
- 逐键、逐值比较（含 fan_table 的 20 项、四牌型的嵌套开关）；
- `dealer_continue_on_win` / `dealer_continue_on_draw` 已作废（03 §3.4），
  只报告"已移除"，不算差异；
- 新 config 不允许出现基线里没有的键（只增字段的豁免清单为空：S6 不新增模板字段）。

用法（工作目录 = code/backend/src）：
    python tools/comparePresets.py            # 与冻结基线对比
    python tools/comparePresets.py --db       # 额外对比库里的预置模板行
    python tools/comparePresets.py --dump     # 打印新 config 全文（排查用）
"""

from __future__ import annotations

import argparse
import json
import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from game.families import registry  # noqa: E402
from game.families.generic.presets import PRESETS, preset_configs  # noqa: E402

LEGACY_PATH = os.path.join(parentdir, "tests", "fixtures", "legacy_presets.json")
# 已作废、只允许"少"不允许"多"的键
REMOVED_KEYS = ("dealer_continue_on_win", "dealer_continue_on_draw")


def _flatten(value, prefix: str = "") -> dict:
    """把嵌套 dict/list 摊平成 `a.b[0].c` → 值，便于逐字段报告差异。"""
    flat: dict = {}
    if isinstance(value, dict):
        for key in value:
            flat.update(_flatten(value[key], f"{prefix}.{key}" if prefix else str(key)))
        if not value:
            flat[prefix] = {}
        return flat
    if isinstance(value, list):
        for index, item in enumerate(value):
            flat.update(_flatten(item, f"{prefix}[{index}]"))
        if not value:
            flat[prefix] = []
        return flat
    flat[prefix] = value
    return flat


def diff_config(legacy: dict, current: dict) -> tuple[list[str], list[str]]:
    """返回 (差异, 已移除键)。差异为空表示逐字段一致。"""
    legacyFlat = _flatten(legacy)
    currentFlat = _flatten(current)
    problems: list[str] = []

    for key, legacyValue in legacyFlat.items():
        if key in REMOVED_KEYS:
            continue
        if key not in currentFlat:
            problems.append(f"缺少字段 {key}（旧值 {legacyValue!r}）")
            continue
        if currentFlat[key] != legacyValue:
            problems.append(f"字段 {key} 变了：旧 {legacyValue!r} → 新 {currentFlat[key]!r}")

    for key, currentValue in currentFlat.items():
        if key not in legacyFlat:
            problems.append(f"新增字段 {key}={currentValue!r}（S6 不允许改变模板形状）")

    removed = [key for key in REMOVED_KEYS if key in legacyFlat]
    return problems, removed


def compareFiles() -> tuple[bool, list[str]]:
    with open(LEGACY_PATH, encoding="utf-8") as handle:
        legacy = json.load(handle)
    current = preset_configs()

    lines: list[str] = []
    ok = True
    missing = [code for code in legacy if code not in current]
    extra = [code for code in current if code not in legacy]
    if missing:
        ok = False
        lines.append(f"[FAIL] 新 config 缺少模板：{', '.join(missing)}")
    if extra:
        ok = False
        lines.append(f"[FAIL] 新 config 多出模板：{', '.join(extra)}")

    for code in sorted(legacy):
        if code not in current:
            continue
        problems, removed = diff_config(legacy[code], current[code])
        head = f"[{'OK  ' if not problems else 'FAIL'}] {code}"
        lines.append(head)
        if removed:
            lines.append(f"       已移除作废字段：{', '.join(removed)}（加载时忽略并记 warning）")
        for problem in problems:
            lines.append(f"       - {problem}")
        if problems:
            ok = False
    return ok, lines


def compareDb() -> tuple[bool, list[str]]:
    """对比库里的预置模板行（需要可用数据库连接）。"""
    from common import mysqlCommon

    lines: list[str] = []
    ok = True
    for preset in PRESETS:
        row = mysqlCommon.query_mj_rule_template_by_code(preset.template_code)
        if not row:
            ok = False
            lines.append(f"[FAIL] 库里没有预置模板 {preset.template_code}")
            continue
        stored = row.get("configJson")
        stored = stored if isinstance(stored, dict) else {}
        problems, removed = diff_config(preset.config, stored)
        lines.append(f"[{'OK  ' if not problems else 'FAIL'}] db:{preset.template_code}")
        if removed:
            lines.append(f"       库里仍残留作废字段：{', '.join(removed)}（S6 加载时忽略）")
        for problem in problems:
            lines.append(f"       - {problem}")
        if problems:
            ok = False
    return ok, lines


def familyRows() -> list[str]:
    lines: list[str] = []
    for plugin in registry.all_families():
        ready, issues = registry.is_ready(plugin.rule_family_code, plugin.capability)
        lines.append(
            f"族 {plugin.rule_family_code:<10} engine={plugin.engine_code:<10} "
            f"tile_set={plugin.capability.get('tile_set')} ready={ready} "
            f"patterns={','.join(plugin.capability.get('patterns') or [])}"
            f"{'' if not issues else ' issues=' + '；'.join(issues)}"
        )
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="预置模板逐字段对比（旧 config ↔ 新 config）")
    parser.add_argument("--db", action="store_true", help="额外对比数据库里的预置模板行")
    parser.add_argument("--dump", action="store_true", help="打印新 config 全文")
    args = parser.parse_args(argv)

    print("== 规则族注册表自检 ==")
    for line in familyRows():
        print("  " + line)

    print("== 预置模板对比（基线 tests/fixtures/legacy_presets.json）==")
    ok, lines = compareFiles()
    for line in lines:
        print("  " + line)

    if args.db:
        print("== 与库内预置模板对比 ==")
        dbOk, dbLines = compareDb()
        ok = ok and dbOk
        for line in dbLines:
            print("  " + line)

    if args.dump:
        print(json.dumps(preset_configs(), ensure_ascii=False, indent=2, sort_keys=True))

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
