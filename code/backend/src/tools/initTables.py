#! /usr/bin/env python3
#encoding: utf-8

#Filename: initTables.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-10-27
#Description:   家庭麻将建表脚本: 按 database/mj_*.txt 经生成器产出的 create_mj_* 逐表建表,
#外加手写段 USER_BASIC(createUserBasic()), 再按 database/indexes.txt 建二级索引,
#最后登记一条 mj_schema_version。
#
#★★ 破坏性操作红线 ★★
#  1. 本脚本只调用 CREATE TABLE IF NOT EXISTS / CREATE INDEX, 禁止任何 drop_*;
#  2. 生成器不提供 migration: 生产改表走「备份 + 测试库演练 + 保留回滚 DDL」;
#  3. 重复执行不报错、不丢数据: 表存在即跳过, 索引先查 information_schema.statistics。
#
#用法(工作目录 = code/backend/src):
#   python tools/initTables.py --env local
#   python tools/initTables.py --env test_server --test --seed
#   python tools/initTables.py --env local --seed

_VERSION = "20261027"
SCHEMA_VERSION_CODE = "20261027_01"
SCHEMA_VERSION_DESC = "S2 初始表结构: USER_BASIC + 14 张 mj_* + 20 条二级索引"

import argparse
import os
import sys
from pathlib import Path

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)


def parseArgs(argv=None):
    parser = argparse.ArgumentParser(description="家庭麻将建表 / 建索引 / 登记结构版本")
    parser.add_argument(
        "--env",
        default="local",
        choices=["local", "test_server", "server_01"],
        help="运行环境，默认 local（与 APP_ENV 联动）",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="指向测试库 mahjong_test（覆盖 .env 里的库名）",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="建表后追加种子：规则族 / 预置模板 / 内置皮肤",
    )
    return parser.parse_args(argv)


def prepareEnv(args):
    """在导入 config/common 之前定环境：APP_ENV 与目标库名。

    test_server 与 --test 都指向测试库 mahjong_test（.env 里即便写了 mahjong_data，
    这里的环境变量优先，避免在建表脚本上误打生产库）。
    """
    os.environ["APP_ENV"] = args.env
    if args.test or args.env == "test_server":
        os.environ["MYSQL_WRITE_DB"] = "mahjong_test"
        os.environ["MYSQL_READ_DB"] = "mahjong_test"


def readIndexes(indexPath):
    """读 indexes.txt：<表名> <索引名> <列1,列2,...>；# 开头为注释。"""
    result = []
    if not indexPath.is_file():
        return result
    for rawLine in indexPath.read_text(encoding="utf-8").splitlines():
        line = rawLine.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(" ")
        if len(parts) != 3:
            raise ValueError(f"indexes.txt 行格式错误(需 3 段): {rawLine}")
        tableName, indexName, columnsText = parts
        columns = [col.strip() for col in columnsText.split(",") if col.strip()]
        if not columns:
            raise ValueError(f"indexes.txt 缺列: {rawLine}")
        for token in [tableName, indexName] + columns:
            if not token.replace("_", "").isalnum():
                raise ValueError(f"indexes.txt 含非法标识符: {token}")
        result.append((tableName, indexName, columns))
    return result


def main(argv=None):
    args = parseArgs(argv)
    prepareEnv(args)

    from common import mysqlCommon as comMysql
    from config import mysqlSettings as mysqlSettings

    srcDir = Path(parentdir)
    indexPath = srcDir / "database" / "indexes.txt"

    print(f"[initTables] env: {mysqlSettings.ENV_NAME}, writeDB: {mysqlSettings.MYSQL_WRITE_DB}, readDB: {mysqlSettings.MYSQL_READ_DB}")
    print(f"[initTables] host: {mysqlSettings.MYSQL_WRITE_HOST}:{mysqlSettings.MYSQL_WRITE_PORT}, poolMax: {mysqlSettings.MYSQL_POOL_MAX}")

    if mysqlSettings.dbW is None or comMysql.mysqlDB is None:
        print("[initTables] 未建立数据库连接(MYSQL_SKIP_CONNECT=1): 请先关闭该开关再执行建表")
        return 1

    if not mysqlSettings.pingServer():
        print("[initTables] 连不上数据库，已中止（请检查 .env 的 MYSQL_* 与实例状态）")
        return 1

    # ---------- 1. 建表 ----------
    okTables = 0
    failTables = []
    for tableName in comMysql.TABLE_NAME_LIST:
        convertor = getattr(comMysql, f"tablename_convertor_{tableName}", None)
        createFunc = getattr(comMysql, f"create_{tableName}", None)
        if convertor is None or createFunc is None:
            failTables.append(tableName)
            print(f"[initTables] MISS {tableName}: 缺少 tablename_convertor_/create_（请先跑生成器并合并）")
            continue
        try:
            existed = comMysql.chkTableExist(tableName)
            result = createFunc(convertor())
            if result:
                okTables += 1
                print(f"[initTables] {'SKIP' if existed else 'OK  '} {tableName}")
            else:
                failTables.append(tableName)
                print(f"[initTables] FAIL {tableName}")
        except Exception as e:
            failTables.append(tableName)
            print(f"[initTables] FAIL {tableName}: {e}")

    # USER_BASIC 是手写段(createUserBasic())
    try:
        existed = comMysql.chkTableExist(comMysql.USER_BASIC_TABLE)
        if comMysql.createUserBasic():
            okTables += 1
            print(f"[initTables] {'SKIP' if existed else 'OK  '} USER_BASIC")
        else:
            failTables.append(comMysql.USER_BASIC_TABLE)
            print("[initTables] FAIL USER_BASIC")
    except Exception as e:
        failTables.append(comMysql.USER_BASIC_TABLE)
        print(f"[initTables] FAIL USER_BASIC: {e}")

    # ---------- 2. 建索引 ----------
    indexList = readIndexes(indexPath)
    existsIndexSet = set()
    rtn = comMysql.mysqlDB.executeRead(
        "SELECT TABLE_NAME AS tableName, INDEX_NAME AS indexName "
        "FROM information_schema.statistics WHERE table_schema = %s",
        (mysqlSettings.MYSQL_WRITE_DB,),
    )
    if rtn > 0:
        for row in comMysql.mysqlDB.fetchAll():
            existsIndexSet.add((row["tableName"], row["indexName"]))

    createdIndexNum = 0
    skippedIndexNum = 0
    failIndexList = []
    for tableName, indexName, columns in indexList:
        if tableName not in comMysql.TABLE_NAME_SET:
            failIndexList.append(f"{tableName}.{indexName}(未登记的表)")
            continue
        if not comMysql.chkTableExist(tableName):
            failIndexList.append(f"{tableName}.{indexName}(表不存在)")
            continue
        if (tableName, indexName) in existsIndexSet:
            skippedIndexNum += 1
            continue
        sqlStr = "CREATE INDEX %s ON %s (%s)" % (indexName, tableName, ",".join(columns))
        try:
            writeRtn = comMysql.mysqlDB.executeWrite(sqlStr)
        except Exception as e:
            writeRtn = -1
            print(f"[initTables] FAIL index {indexName}: {e}")
        if writeRtn >= 0:
            createdIndexNum += 1
            print(f"[initTables] OK   index {indexName} ON {tableName}({','.join(columns)})")
        else:
            failIndexList.append(f"{tableName}.{indexName}")

    # ---------- 3. 结构版本 ----------
    versionTableExisted = comMysql.chkTableExist(comMysql.MJ_SCHEMA_VERSION_TABLE)
    versionRowNum = 0
    if versionTableExisted:
        currList = comMysql.queryTableGeneral(
            comMysql.MJ_SCHEMA_VERSION_TABLE,
            condList=[["versionCode", "=", SCHEMA_VERSION_CODE]],
            order="create",
            limitNum=1,
        )
        if not currList:
            from common import miscCommon as misc

            insertRtn = comMysql.insert_mj_schema_version(
                comMysql.MJ_SCHEMA_VERSION_TABLE,
                {
                    "versionCode": SCHEMA_VERSION_CODE,
                    "description": SCHEMA_VERSION_DESC,
                    "appliedYMDHMS": misc.getTime(),
                    "regID": "initTables",
                },
            )
            print(f"[initTables] schema_version: {SCHEMA_VERSION_CODE} inserted (recID={insertRtn})")
        else:
            print(f"[initTables] schema_version: {SCHEMA_VERSION_CODE} 已存在，跳过")
        cntRtn = comMysql.mysqlDB.executeRead(
            "SELECT COUNT(*) AS num FROM %s" % comMysql.MJ_SCHEMA_VERSION_TABLE
        )
        if cntRtn > 0:
            versionRowNum = int(comMysql.mysqlDB.fetchOne()["num"])

    # ---------- 4. 种子 ----------
    seedInfo = ""
    if args.seed:
        from tools import seedPresets

        counts = seedPresets.installPresets()
        seedInfo = (
            f"rule_family={counts.get('ruleFamily', 0)}, "
            f"rule_template={counts.get('ruleTemplate', 0)}, "
            f"tile_skin={counts.get('tileSkin', 0)}"
        )
        print(f"[initTables] seed: {seedInfo}")

    # ---------- 5. 汇总 ----------
    totalTableNum = len(comMysql.TABLE_NAME_LIST) + 1
    totalIndexNum = len(indexList)
    print(
        "[initTables] done: tables=%d/%d, index created=%d, index skipped=%d, index total=%d, "
        "schema_version_rows=%d, fail=%d"
        % (
            okTables,
            totalTableNum,
            createdIndexNum,
            skippedIndexNum,
            totalIndexNum,
            versionRowNum,
            len(failTables) + len(failIndexList),
        )
    )
    if seedInfo:
        print(f"[initTables] seed counts: {seedInfo}")
    if failTables or failIndexList:
        print(f"[initTables] failed tables: {failTables}; failed indexes: {failIndexList}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
