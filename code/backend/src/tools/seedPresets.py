"""种子数据：规则族 + 预置模板 + 1 个内置皮肤（02 §7）。

口径（S7 起）：
  - 四族（`generic` / `guangdong` / `sichuan` / `baishi`）的 **capability 与预置模板
    一律从 `game/families/registry.py` 取**，这里不再抄第二份，避免「代码与库不同步」；
  - `capabilityJson` 视为代码资产：已存在的族行会被**覆盖成本次注册表的值**
    （否则老库里的旧能力声明会让模板校验与 `ready` 判定跑偏），
    其余列（状态、排序等运营字段）不覆盖；
  - 预置模板只在 templateCode 不存在时插入，`presetFlag='1'`（全局预置、可复制不可改）。

幂等口径：按唯一键（ruleFamilyCode / templateCode / skinCode）先查后插，
重复执行不新增、不报错，也不覆盖家庭后续对预置项的改动。

运行（工作目录 = code/backend/src）：
    python tools/seedPresets.py --env local          # 只灌种子
    python tools/initTables.py --env local --seed    # 建表 + 索引 + 种子
"""

import argparse
import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from common import miscCommon as misc  # noqa: E402
from game.families import registry  # noqa: E402


# 内置皮肤：familyID=0，前端按 CSS 渲染，无逐张资源
BUILTIN_SKIN = {
    "skinCode": "css-classic",
    "skinName": "青玉经典",
    "familyID": 0,
    "previewFileID": None,
    "tileAspect": 0.6667,
    "defaultFlag": "1",
    "skinStatus": "ENABLED",
    "sortOrder": 10,
}


def ruleFamilyRows() -> list[tuple]:
    """(code, 名称, engineCode, tileSetCode, capability, sortOrder, memo)：全部来自注册表。

    注册表就是唯一事实来源：库里多出来的族（历史遗留）不会被删，注册表里缺的族
    也不可能被这里塞进去——`check_capability` 已经在导入期拦过一遍。
    """
    rows: list[tuple] = []
    for plugin in registry.all_families():
        rows.append(
            (
                plugin.rule_family_code,
                plugin.rule_family_name,
                plugin.engine_code,
                plugin.capability.get("tile_set", "136"),
                plugin.capability,
                plugin.sort_order,
                plugin.memo,
            )
        )
    rows.sort(key=lambda row: row[5])
    return rows


def seedRuleFamilies():
    """规则族行；按 ruleFamilyCode 幂等，已存在则只同步 capability 等代码资产。

    返回新增条数（覆盖同步的条数记在日志里，不计入返回值）。
    """
    from common import mysqlCommon as comMysql

    created = 0
    refreshed = 0
    for code, name, engineCode, tileSetCode, capability, sortOrder, memo in ruleFamilyRows():
        row = comMysql.query_mj_rule_family_by_code(code)
        if row:
            current = row.get("capabilityJson") or {}
            if current != capability or str(row.get("engineCode") or "") != engineCode:
                comMysql.update_mj_rule_family(
                    comMysql.MJ_RULE_FAMILY_TABLE,
                    int(row.get("recID") or 0),
                    {
                        "ruleFamilyName": name,
                        "engineCode": engineCode,
                        "tileSetCode": tileSetCode,
                        "capabilityJson": capability,
                        "sortOrder": sortOrder,
                        "memo": memo,
                    },
                )
                refreshed += 1
            continue
        dataSet = {
            "ruleFamilyCode": code,
            "ruleFamilyName": name,
            "engineCode": engineCode,
            "tileSetCode": tileSetCode,
            "capabilityJson": capability,
            "ruleFamilyStatus": "ENABLED",
            "sortOrder": sortOrder,
            "memo": memo,
            "regID": "seedPresets",
            "regYMDHMS": misc.getTime(),
        }
        recID = comMysql.insert_mj_rule_family(comMysql.MJ_RULE_FAMILY_TABLE, dataSet)
        if recID > 0:
            created += 1
    if refreshed:
        print(f"[seedPresets] 已同步 {refreshed} 个族的能力声明")
    return created


def seedRuleTemplates():
    """各族预置模板；familyID=0 / presetFlag=1 / ownerLoginID=NULL，按 templateCode 幂等。

    已存在的**预置**行（familyID=0 且 presetFlag='1'）视为代码资产：`configJson`
    与注册表不一致时覆盖（族能力收紧后，老库里的模板可能带族不再支持的开关，
    开桌会被 `_assertCapability` 拒绝，整族不可用）。家庭复制出来的模板不动。
    """
    from common import mysqlCommon as comMysql

    created = 0
    refreshed = 0
    for plugin in registry.all_families():
        for preset in plugin.presets:
            row = comMysql.queryTableGeneral(
                comMysql.MJ_RULE_TEMPLATE_TABLE,
                condList=[["templateCode", "=", preset.template_code]],
                delFlag="",
                order="create",
                limitNum=1,
            )
            if row:
                current = row[0]
                isPreset = str(current.get("presetFlag") or "") == "1" and int(
                    current.get("familyID") or 0
                ) == 0
                if isPreset and (current.get("configJson") or {}) != (preset.config or {}):
                    comMysql.update_mj_rule_template_fields(
                        int(current.get("recID") or 0),
                        {
                            "templateName": preset.template_name,
                            "description": preset.description,
                            "configJson": preset.config,
                        },
                        "seedPresets",
                    )
                    refreshed += 1
                continue
            dataSet = {
                "templateCode": preset.template_code,
                "familyID": 0,
                "ruleFamilyCode": plugin.rule_family_code,
                "templateName": preset.template_name,
                "description": preset.description,
                "configJson": preset.config,
                "presetFlag": "1",
                "ownerLoginID": None,
                "activeFlag": "1",
                "sortOrder": preset.sort_order,
                "regID": "seedPresets",
                "regYMDHMS": misc.getTime(),
            }
            recID = comMysql.insert_mj_rule_template(
                comMysql.MJ_RULE_TEMPLATE_TABLE, dataSet
            )
            if recID > 0:
                created += 1
    if refreshed:
        print(f"[seedPresets] 已同步 {refreshed} 个预置模板配置")
    return created


def seedTileSkins():
    """1 条内置皮肤（css-classic）：无资源、ENABLED、全局默认；按 skinCode 幂等。

    已存在时只纠正「状态/默认标记」两项代码资产：内置皮肤被误停用后不会出现在
    任何家庭的清单里，前端整站退化成纯 CSS——这属于种子必须保证的基线。
    """
    from common import mysqlCommon as comMysql

    created = 0
    row = comMysql.query_mj_tile_skin_by_code(BUILTIN_SKIN["skinCode"])
    if not row:
        dataSet = dict(BUILTIN_SKIN)
        dataSet["regID"] = "seedPresets"
        dataSet["regYMDHMS"] = misc.getTime()
        recID = comMysql.insert_mj_tile_skin(comMysql.MJ_TILE_SKIN_TABLE, dataSet)
        if recID > 0:
            created += 1
        return created

    fixSet = {}
    if str(row.get("skinStatus") or "") != BUILTIN_SKIN["skinStatus"]:
        fixSet["skinStatus"] = BUILTIN_SKIN["skinStatus"]
    if str(row.get("defaultFlag") or "") != BUILTIN_SKIN["defaultFlag"]:
        fixSet["defaultFlag"] = BUILTIN_SKIN["defaultFlag"]
    if fixSet:
        fixSet["modifyID"] = "seedPresets"
        fixSet["modifyYMDHMS"] = misc.getTime()
        comMysql.update_mj_tile_skin_fields(int(row.get("recID") or 0), fixSet)
    return created


def installPresets():
    """一次性灌全部种子，返回各类新增条数（幂等，可重复调用）。"""
    from config import mysqlSettings as mysqlSettings

    if mysqlSettings.dbW is None:
        raise RuntimeError("未建立数据库连接(MYSQL_SKIP_CONNECT=1)，无法灌种子")

    result = {
        "ruleFamily": seedRuleFamilies(),
        "ruleTemplate": seedRuleTemplates(),
        "tileSkin": seedTileSkins(),
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="灌入规则族 / 预置模板 / 内置皮肤种子")
    parser.add_argument("--env", default="local", choices=["local", "test_server", "server_01"])
    parser.add_argument("--test", action="store_true", help="指向测试库 mahjong_test")
    args = parser.parse_args(argv)

    os.environ["APP_ENV"] = args.env
    if args.test or args.env == "test_server":
        os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
        os.environ["MYSQL_READ_DB"] = "mahjong_test"

    counts = installPresets()
    print(
        "[seedPresets] env:%s db:%s -> %s"
        % (
            os.environ.get("APP_ENV"),
            os.environ.get("MYSQL_WRITE_DB", ""),
            counts,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
