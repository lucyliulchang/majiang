"""一次性补数：为已有柏氏模板补「海底捞」番种（07 §5 v1.15 / R-9）。

背景：番表是**模板快照**（`RuleConfig.fan_table` 落在 `mj_rule_template.configJson`），
新增番种只改代码不会回溯已有模板。`tools/seedPresets.py` 只刷新全局预置行
（`familyID=0` 且 `presetFlag='1'`），**家庭复制出来的模板不会被刷新**；而
`game/fan.py::evaluate()` 对「模板里没有的番种 id」是**静默跳过**——新加的
「海底捞 50 番」会被无声吞掉，表现为「最后一张不是 1 筒自摸也不加番」。

口径（幂等，可重复执行）：
  - 只处理 `ruleFamilyCode='baishi'` 的模板（含预置行与家庭复制行）；
  - `configJson.fan_table` 已含 `hai_di_lao` → 跳过（不改已有番值，尊重家庭自定义）；
  - 缺失时插到 `hai_di_lao_yue` **之后**（与 07 §5 行序、`FAN_TABLE` 元组序一致）；
    若连 `hai_di_lao_yue` 都没有（异常模板）→ 追加到末尾；
  - 写库前用 `baishi.RuleConfig` 校验一遍，校验不过只报错不写。

运行（工作目录 = code/backend/src）：
    python tools/backfillBaishiHaiDiLao.py --env local
    python tools/backfillBaishiHaiDiLao.py --env server_01 --dry-run
"""

import argparse
import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from game.families.baishi.config import RuleConfig  # noqa: E402
from game.families.baishi.fan import FAN_DEFAULTS  # noqa: E402

FAN_ID = "hai_di_lao"
ANCHOR_ID = "hai_di_lao_yue"
MAX_TEMPLATES = 100  # queryTableGeneral 的 limitNum 上限


def _fan_row() -> dict:
    """从 `FAN_TABLE` 取「海底捞」行，转成 `configJson.fan_table` 的行形状。"""
    for fid, name, fan, group, stackable in FAN_DEFAULTS:
        if fid == FAN_ID:
            return {
                "id": fid,
                "name": name,
                "fan": fan,
                "exclusive_group": group,
                "stackable": stackable,
            }
    raise RuntimeError(f"FAN_TABLE 里没有 {FAN_ID}，请先确认 baishi/fan.py 已升级")


def _with_fan_row(config: dict, row: dict) -> dict | None:
    """返回补全后的 config（不修改入参）；已存在或结构异常时返回 None。"""
    fan_table = config.get("fan_table")
    if not isinstance(fan_table, list):
        return None
    if any(isinstance(item, dict) and item.get("id") == FAN_ID for item in fan_table):
        return None
    anchor = next(
        (
            index
            for index, item in enumerate(fan_table)
            if isinstance(item, dict) and item.get("id") == ANCHOR_ID
        ),
        None,
    )
    patched = list(fan_table)
    if anchor is None:
        patched.append(row)
    else:
        patched.insert(anchor + 1, row)
    return {**config, "fan_table": patched}


def backfill(dry_run: bool = False) -> dict:
    from common import miscCommon as misc
    from common import mysqlCommon as comMysql

    rows = comMysql.queryTableGeneral(
        comMysql.MJ_RULE_TEMPLATE_TABLE,
        condList=[["ruleFamilyCode", "=", "baishi"]],
        delFlag="",
        order="create",
        limitNum=MAX_TEMPLATES,
    )
    row_shape = _fan_row()
    result = {"scanned": len(rows), "updated": 0, "skipped": 0, "invalid": 0, "dry_run": dry_run}
    for current in rows:
        rec_id = int(current.get("recID") or 0)
        code = str(current.get("templateCode") or "")
        config = current.get("configJson")
        if not rec_id or not isinstance(config, dict):
            result["skipped"] += 1
            continue
        patched = _with_fan_row(config, row_shape)
        if patched is None:
            result["skipped"] += 1
            continue
        try:
            RuleConfig.model_validate(patched)
        except Exception as exc:  # noqa: BLE001 —— 只报错不写，避免写坏模板
            result["invalid"] += 1
            print(f"[backfill] {code}(recID={rec_id}) 校验失败，跳过：{exc}")
            continue
        if dry_run:
            result["updated"] += 1
            print(f"[backfill] {code}(recID={rec_id}) 待补 {FAN_ID}（dry-run，未写库）")
            continue
        written = comMysql.update_mj_rule_template_fields(
            rec_id,
            {"configJson": patched},
            "backfillHaiDiLao",
        )
        if written:
            result["updated"] += 1
            print(f"[backfill] {code}(recID={rec_id}) 已补 {FAN_ID}")
        else:
            result["invalid"] += 1
            print(f"[backfill] {code}(recID={rec_id}) 写库失败")
    if result["scanned"] >= MAX_TEMPLATES:
        print(f"[backfill] 注意：只扫描了前 {MAX_TEMPLATES} 条，请确认模板总数")
    print(f"[backfill] {misc.getTime()} -> {result}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="为柏氏模板 configJson.fan_table 补齐「海底捞」番种")
    parser.add_argument("--env", default="local", choices=["local", "test_server", "server_01"])
    parser.add_argument("--test", action="store_true", help="指向测试库 mahjong_test")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要修改的模板，不写库")
    args = parser.parse_args(argv)

    os.environ["APP_ENV"] = args.env
    if args.test or args.env == "test_server":
        os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
        os.environ["MYSQL_READ_DB"] = "mahjong_test"

    backfill(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
