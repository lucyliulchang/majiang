"""种子数据：规则族 + 预置模板 + 1 个内置皮肤（02 §7）。

口径（S6 起）：
  - 已接入的族（`generic` / `guangdong`）的 **capability 与预置模板一律从
    `game/families/registry.py` 取**，不再在这里抄一份，避免「代码与库不同步」；
  - 尚未接入引擎的族（`sichuan` / `baishi`，S7 落地）先按 03 §2.2 冻结能力声明；
    它们可以出现在族清单里，但 `ready=false`，开桌返回 `RULE_FAMILY_NOT_READY`。

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

# 尚未接入引擎的族（S7 才有 engine.py）：能力声明按 03 §5/§6/§7 冻结
_PENDING_FAMILIES = [
    (
        "sichuan",
        "四川血战到底",
        "sichuan",
        "108",
        {
            "tile_set": "108",
            "allow_chow": False,
            "honors": False,
            "wind_fan": False,
            "patterns": ["standard", "seven_pairs"],
            "fan_combine": ["group_best"],
            "fan_modes": ["linear", "exponential"],
            "fan_cap_allowed": True,
            "fan_cap_max": 30,
            "switches": ["turn_timeout", "kong_score", "ting_hint", "draw_penalty"],
            "settlement": ["self_draw", "discard", "draw", "kong", "rob_kong"],
            "multi_winner": True,
            "bao_pai": False,
            "self_draw_multiplier": 1,
            "dealer_multiplier": {"win": 1, "pay": 1},
            "lack_suit": True,
            "min_fan_to_win": 0,
            "max_rounds": 4,
        },
        40,
        "108 张（无字牌），缺一门，可多人胡",
    ),
    (
        "baishi",
        "柏氏规则",
        "baishi",
        "136",
        {
            "tile_set": "136",
            "allow_chow": True,
            "honors": True,
            "wind_fan": True,
            "patterns": ["standard", "seven_pairs", "thirteen_unrelated", "thirteen_orphans"],
            "fan_combine": ["sum_all"],
            "fan_modes": ["linear"],
            "fan_cap_allowed": False,
            "fan_cap_max": 0,
            "switches": ["turn_timeout", "kong_score", "pause"],
            "settlement": ["self_draw", "discard", "draw", "kong", "rob_kong", "bao_pai"],
            "multi_winner": False,
            "bao_pai": {
                "supported": True,
                "win_type": "discard",
                "min_exposed_melds": 3,
                "patterns": ["qing_yi_se", "hun_yi_se", "quan_zi", "quan_yao"],
                "payer": "discarder_full",
            },
            "dealer_multiplier": {"win": 2, "pay": 2},
            "self_draw_multiplier": 2,
            "lack_suit": False,
            "min_fan_to_win": 1,
            "max_rounds": 4,
        },
        20,
        "累计不乘积、不封顶、包牌独付，细则见 07",
    ),
]


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
    """(code, 名称, engineCode, tileSetCode, capability, sortOrder, memo)：注册表优先。"""
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
    rows.extend(_PENDING_FAMILIES)
    rows.sort(key=lambda row: row[5])
    return rows


def _exists(tableName, columnName, value):
    from common import mysqlCommon as comMysql

    rows = comMysql.queryTableGeneral(
        tableName, condList=[[columnName, "=", value]], order="create", limitNum=1
    )
    return bool(rows)


def seedRuleFamilies():
    """规则族行；按 ruleFamilyCode 幂等。返回新增条数。"""
    from common import mysqlCommon as comMysql

    created = 0
    for code, name, engineCode, tileSetCode, capability, sortOrder, memo in ruleFamilyRows():
        if _exists(comMysql.MJ_RULE_FAMILY_TABLE, "ruleFamilyCode", code):
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
    return created


def seedRuleTemplates():
    """各族预置模板；familyID=0 / presetFlag=1 / ownerLoginID=NULL，按 templateCode 幂等。"""
    from common import mysqlCommon as comMysql

    created = 0
    for plugin in registry.all_families():
        for preset in plugin.presets:
            if _exists(comMysql.MJ_RULE_TEMPLATE_TABLE, "templateCode", preset.template_code):
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
    return created


def seedTileSkins():
    """1 条内置皮肤；按 skinCode 幂等。"""
    from common import mysqlCommon as comMysql

    created = 0
    if not _exists(comMysql.MJ_TILE_SKIN_TABLE, "skinCode", BUILTIN_SKIN["skinCode"]):
        dataSet = dict(BUILTIN_SKIN)
        dataSet["regID"] = "seedPresets"
        dataSet["regYMDHMS"] = misc.getTime()
        recID = comMysql.insert_mj_tile_skin(comMysql.MJ_TILE_SKIN_TABLE, dataSet)
        if recID > 0:
            created += 1
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
