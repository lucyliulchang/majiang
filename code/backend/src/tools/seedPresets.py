"""种子数据：4 个规则族 + 4 套通用族预置模板 + 1 个内置皮肤（02 §7）。

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

# 规则族能力声明（03 §2.2 / 07 §11）：只增不改语义，新增字段必须有默认值
_GENERIC_CAPABILITY = {
    "tile_set": "136",
    "allow_chow": True,
    "honors": True,
    "wind_fan": True,
    "patterns": ["standard", "seven_pairs", "thirteen_orphans", "thirteen_unrelated"],
    "fan_combine": ["group_best"],
    "fan_modes": ["linear", "exponential"],
    "fan_cap_allowed": True,
    "fan_cap_max": 30,
    "switches": ["turn_timeout", "kong_score", "ting_hint", "draw_penalty"],
    "settlement": ["self_draw", "discard", "draw", "kong", "rob_kong"],
    "multi_winner": False,
    "bao_pai": False,
    "self_draw_multiplier": 1,
    "dealer_multiplier": {"win": 1, "pay": 1},
    "lack_suit": False,
    "min_fan_to_win": 0,
    "max_rounds": 4,
}

_GUANGDONG_CAPABILITY = {
    **_GENERIC_CAPABILITY,
    "wind_fan": False,
    "patterns": ["standard", "seven_pairs", "thirteen_orphans"],
}

_SICHUAN_CAPABILITY = {
    **_GENERIC_CAPABILITY,
    "tile_set": "108",
    "allow_chow": False,
    "honors": False,
    "wind_fan": False,
    "patterns": ["standard", "seven_pairs"],
    "multi_winner": True,
    "lack_suit": True,
}

# 柏氏：累计不乘积、不封顶、自摸×2、庄家×2、包牌独付（07 §11 逐字段照抄）
_BAISHI_CAPABILITY = {
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
}

# ruleFamilyCode, 名称, engineCode, tileSetCode, capability, sortOrder, memo
RULE_FAMILIES = [
    ("generic", "通用家庭标准", "generic", "136", _GENERIC_CAPABILITY, 10, "完整复刻现有 RuleConfig 语义，作为回归基线"),
    ("guangdong", "广东推倒胡", "guangdong", "136", _GUANGDONG_CAPABILITY, 30, "136 张（含字牌），可吃，简化番表"),
    ("sichuan", "四川血战到底", "sichuan", "108", _SICHUAN_CAPABILITY, 40, "108 张（无字牌），缺一门，可多人胡"),
    ("baishi", "柏氏规则", "baishi", "136", _BAISHI_CAPABILITY, 20, "累计不乘积、不封顶、包牌独付，细则见 07"),
]


def _ruleConfig(**overrides):
    """按 schemas.rule.RuleConfig 生成模板 config（走强校验，避免种子写坏数据）。

    03 §4.1 已移除 dealer_continue_on_win/draw，这里统一剔除；
    其余键与 RuleConfig 默认值一致，保证「现状」模板读出来语义不变。
    """
    from schemas.rule import RuleConfig

    config = RuleConfig(**overrides).model_dump()
    config.pop("dealer_continue_on_win", None)
    config.pop("dealer_continue_on_draw", None)
    return config


def _presetTemplates():
    from schemas.rule import KongScore, PatternSwitches, ThirteenUnrelatedOptions, ToggleValue, TurnTimeout

    standard = _ruleConfig(
        base_score=1,
        fan_mode="exponential",
        fan_cap=8,
        allow_chow=True,
        turn_timeout=TurnTimeout(enabled=True, seconds=15),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    no_chow = _ruleConfig(
        base_score=1,
        fan_mode="linear",
        fan_cap=12,
        allow_chow=False,
        turn_timeout=TurnTimeout(enabled=True, seconds=20),
        kong_score=KongScore(enabled=True, exposed=2, hidden=4, added=2),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    with_unrelated = _ruleConfig(
        base_score=1,
        fan_mode="exponential",
        fan_cap=10,
        allow_chow=True,
        patterns=PatternSwitches(
            standard=True,
            seven_pairs=True,
            thirteen_orphans=True,
            thirteen_unrelated=ThirteenUnrelatedOptions(
                enabled=True, require_all_honors=False, allow_pair=True, min_gap=3
            ),
        ),
        turn_timeout=TurnTimeout(enabled=True, seconds=18),
        kong_score=KongScore(enabled=True, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=True),
        rounds_per_game=4,
    )
    casual = _ruleConfig(
        base_score=1,
        fan_mode="linear",
        fan_cap=15,
        allow_chow=True,
        turn_timeout=TurnTimeout(enabled=False, seconds=15),
        kong_score=KongScore(enabled=False, exposed=1, hidden=2, added=1),
        ting_hint=ToggleValue(enabled=False),
        draw_penalty=ToggleValue(enabled=False, value=0),
        rounds_per_game=4,
    )
    return [
        ("generic_standard", "家庭标准", "底分 1，2 的 N 次方封顶 8 番，可以吃，限时 15 秒，杠分 1-2-1", standard, 10),
        ("generic_no_chow", "宽松无吃", "不能吃只能碰，线性累加封顶 12 番，适合新手慢慢打", no_chow, 20),
        ("generic_unrelated", "带十三不靠", "在家庭标准基础上开放十三不靠，需要 4 张牌间隔至少 3 位", with_unrelated, 30),
        ("generic_casual", "休闲不限时", "出牌不限时、杠不计分、无听牌提示，纯粹图个乐", casual, 40),
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


def _exists(tableName, columnName, value):
    from common import mysqlCommon as comMysql

    rows = comMysql.queryTableGeneral(
        tableName, condList=[[columnName, "=", value]], order="create", limitNum=1
    )
    return bool(rows)


def seedRuleFamilies():
    """4 条规则族；按 ruleFamilyCode 幂等。返回新增条数。"""
    from common import mysqlCommon as comMysql

    created = 0
    for code, name, engineCode, tileSetCode, capability, sortOrder, memo in RULE_FAMILIES:
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
    """4 套通用族预置模板；familyID=0 / presetFlag=1 / ownerLoginID=NULL，按 templateCode 幂等。"""
    from common import mysqlCommon as comMysql

    created = 0
    for templateCode, name, description, config, sortOrder in _presetTemplates():
        if _exists(comMysql.MJ_RULE_TEMPLATE_TABLE, "templateCode", templateCode):
            continue
        dataSet = {
            "templateCode": templateCode,
            "familyID": 0,
            "ruleFamilyCode": "generic",
            "templateName": name,
            "description": description,
            "configJson": config,
            "presetFlag": "1",
            "ownerLoginID": None,
            "activeFlag": "1",
            "sortOrder": sortOrder,
            "regID": "seedPresets",
            "regYMDHMS": misc.getTime(),
        }
        recID = comMysql.insert_mj_rule_template(comMysql.MJ_RULE_TEMPLATE_TABLE, dataSet)
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


def install_presets(session):
    """SQLAlchemy / SQLite 兼容入口（S2 保留，S5 切测试库后删除）。

    仍走旧口径：按模板名去重、只写 RuleTemplate；供 main/app.py、tests/test_ws_flow.py
    与 scripts/bootstrap_family.py 沿用，避免本步改动业务启动与测试执行方式。
    """
    from sqlalchemy import select

    from db.models import RuleTemplate

    created = 0
    existing = {
        row.name
        for row in session.scalars(
            select(RuleTemplate).where(RuleTemplate.is_preset.is_(True))
        ).all()
    }
    for _templateCode, name, description, config, _sortOrder in _presetTemplates():
        if name in existing:
            continue
        session.add(
            RuleTemplate(
                owner_id=None,
                name=name,
                description=description,
                config=config,
                is_preset=True,
                is_active=True,
            )
        )
        created += 1
    if created:
        session.commit()
    return created


def main(argv=None):
    import argparse

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
