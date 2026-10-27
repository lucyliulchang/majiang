#! /usr/bin/env python3
#encoding: utf-8

#Filename: dataClean.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-10-27
#Description:   定时数据清理(由 crontab -> restore_clean.sh 拉起, 每日 04:00)
#               设计要点:
#                 1) 不归档: 所有到期数据在本脚本内直接物理删除, 无月度/人工环节
#                 2) 默认 dry-run, 只打印候选条数; cron 由 restore_clean.sh 传 --apply
#                 3) 每批独立事务并提交(DELETE ... ORDER BY recID LIMIT n), 禁止长事务,
#                    避免清理期间 /api/health 超时被 monitor 误杀
#                 4) 删除表白名单 + 永久保护名单硬编码, 任何表名不在白名单内一律拒绝执行
#                 5) 退出码: 0 全部成功, 1 有 tag 失败(供 cron/MAILTO 告警)
#
#               用法:
#                 python schedule/dataClean.py                       # dry-run, 输出候选条数
#                 python schedule/dataClean.py --apply               # 实际删除(cron 用)
#                 python schedule/dataClean.py --only messages,files # 只跑指定 tag
#                 python schedule/dataClean.py --apply --batch-size 2000 --max-batches 10
#
#               注: 清理脚本直连 pymysql(与 tools/initTables.py 同一定位), 不经
#                   common/mysqlCommon 的业务函数; 原因是一批批 DELETE 属于运维动作,
#                   不参与业务事务, 也不该出现在业务数据层。

_VERSION = "20261027"

_USAGE = """用法:
  python schedule/dataClean.py                        # dry-run, 只输出候选条数
  python schedule/dataClean.py --apply                # 实际删除(cron 用)
  python schedule/dataClean.py --only messages,files  # 只跑指定 tag
  python schedule/dataClean.py --apply --batch-size 2000 --max-batches 10
可用 tag: messages games rooms audit softDeleted files report"""

import os
import sys
import time
import pymysql

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # code/backend/src
_BACKEND_DIR = os.path.dirname(_SRC_DIR)                                 # code/backend
sys.path.insert(0, _SRC_DIR)

import logging

_LOG = logging.getLogger("MAHJONG.DATACLEAN")

#时区与格式: 与表内 YMDHMS(VARCHAR(16), Asia/Shanghai) 保持一致
_YMDHMS_FMT = "%Y%m%d%H%M%S"

#统计汇总
_statList = []


#配置 begin

def loadEnvFile(fileName):
    """极简 .env 读取(KEY=VALUE), 已存在的环境变量优先, 不覆盖"""
    result = {}
    try:
        with open(fileName, "r", encoding="utf-8") as hFile:
            for line in hFile:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                #带引号按原样取值(口令可能含 #), 否则只裁掉 " #" 之后的注释
                if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
                    value = value[1:-1]
                else:
                    value = value.split(" #", 1)[0].strip()
                if key:
                    result[key] = value
    except FileNotFoundError:
        pass
    except Exception as e:
        _LOG.warning(f"loadEnvFile failed:{fileName},{e}")
    return result


_ENV_FILE = loadEnvFile(os.path.join(_SRC_DIR, ".env"))


def getEnv(key, default=""):
    value = os.environ.get(key)
    if value is None or value == "":
        value = _ENV_FILE.get(key, default)
    return value


def getEnvInt(key, default):
    try:
        return int(getEnv(key, str(default)))
    except (TypeError, ValueError):
        return default


#保留期(天): 全部可被 .env 覆盖, 不散落在函数体内
DATA_RETENTION_DAYS = getEnvInt("DATA_RETENTION_DAYS", 1095)          #战绩/审计: 3 年
MESSAGE_RETENTION_DAYS = getEnvInt("MESSAGE_RETENTION_DAYS", 180)     #聊天与播报: 180 天
SOFT_DELETE_PURGE_DAYS = getEnvInt("SOFT_DELETE_PURGE_DAYS", 30)      #软删: 30 天后物理删
ORPHAN_FILE_DAYS = getEnvInt("ORPHAN_FILE_DAYS", 30)                  #孤儿文件: 30 天
BATCH_SIZE = getEnvInt("SCHEDULE_BATCH_SIZE", 5000)
MAX_BATCHES = getEnvInt("SCHEDULE_MAX_BATCHES", 20)

#前端直访图片目录(生产 /data/webserver/majiangapp)，皮肤在 tiles/ 下
UPLOAD_DIR = getEnv("UPLOAD_DIR", os.path.join(_BACKEND_DIR, "data", "webserver", "majiangapp"))
if not os.path.isabs(UPLOAD_DIR):
    UPLOAD_DIR = os.path.normpath(os.path.join(_SRC_DIR, UPLOAD_DIR))

#只允许在这些表上执行物理删除(白名单)
SAFE_DELETE_TABLES = (
    "mj_room_message",
    "mj_game_round",
    "mj_game_player",
    "mj_game",
    "mj_room",
    "mj_audit_log",
    "mj_rule_template",
    "mj_tile_skin",
    "mj_tile_skin_asset",
)

#永久保护(只做说明用, 白名单已排除): USER_BASIC / mj_family / mj_family_member /
#mj_user_pref / mj_rule_family / mj_schema_version / familyID=0 的模板与皮肤

#配置 end


#基础工具 begin

def getNowYMDHMS(offsetDays=0):
    return time.strftime(_YMDHMS_FMT, time.localtime(time.time() - offsetDays * 86400))


def getLimitYMDHMS(days):
    """早于该时间的记录视为过期"""
    return time.strftime(_YMDHMS_FMT, time.localtime(time.time() - days * 86400))


def getTableName(dbName, tableName):
    return f"`{dbName}`.`{tableName}`"


def chkTableName(tableName):
    if tableName not in SAFE_DELETE_TABLES:
        raise RuntimeError(f"table[{tableName}] 不在删除白名单内, 拒绝执行")
    return tableName


def connectDB():
    dbName = getEnv("MYSQL_WRITE_DB", "mahjong_data")
    conn = pymysql.connect(
        host=getEnv("MYSQL_WRITE_HOST", "127.0.0.1"),
        port=getEnvInt("MYSQL_WRITE_PORT", 3306),
        user=getEnv("MYSQL_WRITE_USER", "mjapp"),
        password=getEnv("MYSQL_WRITE_PASSWD", ""),
        database=dbName,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=5,
        read_timeout=30,
        write_timeout=30,
    )
    return conn, dbName


def queryCount(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return int(row[0]) if row else 0


def executeDelete(conn, dbName, tableName, whereSql, whereParams, limitNum):
    """单批删除, autocommit 下提交, 返回影响行数"""
    chkTableName(tableName)
    sql = (f"DELETE FROM {getTableName(dbName, tableName)} "
           f"WHERE {whereSql} ORDER BY recID LIMIT {int(limitNum)}")
    with conn.cursor() as cur:
        return cur.execute(sql, whereParams)


def deleteInBatches(conn, dbName, tableName, whereSql, whereParams, applyFlag):
    """循环批量删除, 返回 (候选数, 删除数, 是否跑满上限)"""
    countSql = f"SELECT COUNT(*) FROM {getTableName(dbName, tableName)} WHERE {whereSql}"
    candidates = queryCount(conn, countSql, whereParams)

    if not applyFlag:
        return candidates, 0, False

    deleted = 0
    batchNo = 0
    while batchNo < MAX_BATCHES:
        batchNo += 1
        rows = executeDelete(conn, dbName, tableName, whereSql, whereParams, BATCH_SIZE)
        deleted += rows
        if rows < BATCH_SIZE:
            return candidates, deleted, False
        time.sleep(0.1)

    return candidates, deleted, True


def addStat(tag, candidates, deleted, truncated=False, note=""):
    _statList.append({
        "tag": tag,
        "candidates": candidates,
        "deleted": deleted,
        "truncated": truncated,
        "note": note,
    })
    flag = "TRUNCATED" if truncated else "ok"
    _LOG.info(f"[{tag}] candidates:{candidates}, deleted:{deleted}, status:{flag}"
              + (f", {note}" if note else ""))

#基础工具 end


#tag: 聊天与系统播报 begin

def cleanMessages(conn, dbName, applyFlag):
    """mj_room_message 按时间清理; 跳过仍在 OPEN 的房, 避免把进行中的牌桌聊天删掉"""
    limitYMDHMS = getLimitYMDHMS(MESSAGE_RETENTION_DAYS)
    whereSql = "createdYMDHMS < %s"
    whereParams = [limitYMDHMS]

    openRooms = queryCount(conn, f"SELECT COUNT(*) FROM {getTableName(dbName, 'mj_room')} "
                                 "WHERE roomStatus = 'OPEN' AND delFlag = '0'")
    if openRooms:
        with conn.cursor() as cur:
            cur.execute(f"SELECT recID FROM {getTableName(dbName, 'mj_room')} "
                        "WHERE roomStatus = 'OPEN' AND delFlag = '0'")
            roomIDList = [int(row[0]) for row in cur.fetchall()]
        if roomIDList:
            placeholders = ",".join(["%s"] * len(roomIDList))
            whereSql += f" AND roomID NOT IN ({placeholders})"
            whereParams.extend(roomIDList)

    candidates, deleted, truncated = deleteInBatches(
        conn, dbName, "mj_room_message", whereSql, whereParams, applyFlag)
    addStat("messages", candidates, deleted, truncated, f"before:{limitYMDHMS}")

#tag: 聊天与系统播报 end


#tag: 战绩(场次/座位/逐局) begin

def cleanGames(conn, dbName, applyFlag):
    """三年以上的已结束场次: 逐局 -> 座位 -> 场次, 每批一个事务; 永远不碰 PLAYING"""
    limitYMDHMS = getLimitYMDHMS(DATA_RETENTION_DAYS)
    whereSql = "gameStatus IN ('FINISHED','ABORTED') AND startedYMDHMS < %s"
    whereParams = [limitYMDHMS]

    countSql = (f"SELECT COUNT(*) FROM {getTableName(dbName, 'mj_game')} "
                f"WHERE {whereSql}")
    candidates = queryCount(conn, countSql, whereParams)

    if not applyFlag:
        addStat("games", candidates, 0, False, f"before:{limitYMDHMS}")
        return

    deleted = 0
    batchNo = 0
    truncated = False
    while True:
        if batchNo >= MAX_BATCHES:
            truncated = True
            break
        batchNo += 1

        with conn.cursor() as cur:
            cur.execute(f"SELECT recID FROM {getTableName(dbName, 'mj_game')} "
                        f"WHERE {whereSql} ORDER BY recID LIMIT {int(BATCH_SIZE)}",
                        whereParams)
            gameIDList = [int(row[0]) for row in cur.fetchall()]
        if not gameIDList:
            break

        placeholders = ",".join(["%s"] * len(gameIDList))
        conn.begin()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {getTableName(dbName, 'mj_game_round')} "
                            f"WHERE gameID IN ({placeholders})", gameIDList)
                cur.execute(f"DELETE FROM {getTableName(dbName, 'mj_game_player')} "
                            f"WHERE gameID IN ({placeholders})", gameIDList)
                cur.execute(f"DELETE FROM {getTableName(dbName, 'mj_game')} "
                            f"WHERE recID IN ({placeholders})", gameIDList)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        deleted += len(gameIDList)
        if len(gameIDList) < BATCH_SIZE:
            break
        time.sleep(0.1)

    addStat("games", candidates, deleted, truncated, f"before:{limitYMDHMS}")

#tag: 战绩(场次/座位/逐局) end


#tag: 房间 begin

def cleanRooms(conn, dbName, applyFlag):
    """关闭且无场次引用的房; 必须放在 games 之后, 否则会删掉仍有战绩的房"""
    limitYMDHMS = getLimitYMDHMS(DATA_RETENTION_DAYS)
    whereSql = ("roomStatus = 'CLOSED' AND closedYMDHMS IS NOT NULL AND closedYMDHMS < %s "
                "AND recID NOT IN (SELECT roomID FROM " + getTableName(dbName, "mj_game") + ")")
    whereParams = [limitYMDHMS]

    candidates, deleted, truncated = deleteInBatches(
        conn, dbName, "mj_room", whereSql, whereParams, applyFlag)
    addStat("rooms", candidates, deleted, truncated, f"before:{limitYMDHMS}")

#tag: 房间 end


#tag: 审计 begin

def cleanAuditLog(conn, dbName, applyFlag):
    limitYMDHMS = getLimitYMDHMS(DATA_RETENTION_DAYS)
    candidates, deleted, truncated = deleteInBatches(
        conn, dbName, "mj_audit_log", "createdYMDHMS < %s", [limitYMDHMS], applyFlag)
    addStat("audit", candidates, deleted, truncated, f"before:{limitYMDHMS}")

#tag: 审计 end


#tag: 软删记录 begin

def cleanSoftDeleted(conn, dbName, applyFlag):
    """软删满 30 天的家庭自定义模板与皮肤; 皮肤连同资源行一并删, 文件交给 files tag"""
    limitYMDHMS = getLimitYMDHMS(SOFT_DELETE_PURGE_DAYS)
    deletedTotal = 0
    candidatesTotal = 0
    truncated = False

    #家庭自定义模板(familyID>0), 全局预置不动
    sql = "delFlag = '1' AND familyID > 0 AND modifyYMDHMS < %s"
    candidates, deleted, truncated = deleteInBatches(
        conn, dbName, "mj_rule_template", sql, [limitYMDHMS], applyFlag)
    candidatesTotal += candidates
    deletedTotal += deleted

    #家庭自定义皮肤 + 资源
    sql = "delFlag = '1' AND familyID > 0 AND modifyYMDHMS < %s"
    candidates = queryCount(conn, f"SELECT COUNT(*) FROM {getTableName(dbName, 'mj_tile_skin')} "
                                  f"WHERE {sql}", [limitYMDHMS])
    candidatesTotal += candidates

    if applyFlag and candidates:
        with conn.cursor() as cur:
            cur.execute(f"SELECT recID FROM {getTableName(dbName, 'mj_tile_skin')} "
                        f"WHERE {sql} ORDER BY recID LIMIT {int(BATCH_SIZE)}", [limitYMDHMS])
            skinIDList = [int(row[0]) for row in cur.fetchall()]
        if skinIDList:
            placeholders = ",".join(["%s"] * len(skinIDList))
            conn.begin()
            try:
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM {getTableName(dbName, 'mj_tile_skin_asset')} "
                                f"WHERE skinID IN ({placeholders})", skinIDList)
                    cur.execute(f"DELETE FROM {getTableName(dbName, 'mj_tile_skin')} "
                                f"WHERE recID IN ({placeholders})", skinIDList)
                conn.commit()
                deletedTotal += len(skinIDList)
            except Exception:
                conn.rollback()
                raise
            
    addStat("softDeleted", candidatesTotal, deletedTotal, truncated, f"before:{limitYMDHMS}")

#tag: 软删记录 end


#tag: 孤儿文件 begin

def collectReferencedFiles(conn, dbName):
    """DB 里仍被引用的文件相对路径集合"""
    result = set()

    with conn.cursor() as cur:
        cur.execute(f"SELECT fileID, thumbFileID FROM {getTableName(dbName, 'mj_tile_skin_asset')}")
        for fileID, thumbFileID in cur.fetchall():
            for item in (fileID, thumbFileID):
                if item:
                    result.add(str(item).replace("\\", "/").lstrip("./"))
        cur.execute(f"SELECT previewFileID FROM {getTableName(dbName, 'mj_tile_skin')}")
        for (previewFileID,) in cur.fetchall():
            if previewFileID:
                result.add(str(previewFileID).replace("\\", "/").lstrip("./"))

    return result


def cleanOrphanFiles(conn, dbName, applyFlag):
    """删 DB 无引用且 mtime 超过 ORPHAN_FILE_DAYS 的文件, 再清空目录"""
    tileRoot = os.path.join(UPLOAD_DIR, "tiles")
    if not os.path.isdir(tileRoot):
        addStat("files", 0, 0, False, f"skip, no dir:{tileRoot}")
        return

    referenced = collectReferencedFiles(conn, dbName)
    expireTime = time.time() - ORPHAN_FILE_DAYS * 86400

    candidates = 0
    deleted = 0
    deletedBytes = 0
    for dirPath, _dirNames, fileNames in os.walk(tileRoot):
        for fileName in fileNames:
            filePath = os.path.join(dirPath, fileName)
            relativePath = os.path.relpath(filePath, UPLOAD_DIR).replace("\\", "/")
            try:
                stat = os.stat(filePath)
            except OSError:
                continue
            if relativePath in referenced:
                continue
            if stat.st_mtime >= expireTime:
                continue

            candidates += 1
            if not applyFlag:
                continue
            try:
                os.remove(filePath)
                deleted += 1
                deletedBytes += stat.st_size
            except OSError as e:
                _LOG.warning(f"remove failed:{filePath},{e}")

    if applyFlag:
        #自底向上清空目录
        for dirPath, _dirNames, _fileNames in os.walk(tileRoot, topdown=False):
            if os.path.normpath(dirPath) == os.path.normpath(tileRoot):
                continue
            try:
                if not os.listdir(dirPath):
                    os.rmdir(dirPath)
            except OSError:
                pass

    addStat("files", candidates, deleted, False, f"bytes:{deletedBytes}")

#tag: 孤儿文件 end


#tag: 体检 begin

def reportTables(conn, dbName):
    sql = ("SELECT table_name, table_rows, data_length, index_length "
           "FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name")
    with conn.cursor() as cur:
        cur.execute(sql, [dbName])
        rows = cur.fetchall()

    _LOG.info("report: table_rows/data_kb/index_kb")
    for tableName, tableRows, dataLength, indexLength in rows:
        _LOG.info(f"report: {tableName:24s} {int(tableRows or 0):>8d} "
                  f"{int(dataLength or 0) // 1024:>8d}K {int(indexLength or 0) // 1024:>8d}K")

    addStat("report", len(rows), 0, False, f"tables:{len(rows)}")

#tag: 体检 end


#主流程 begin

TAG_ORDER = ["messages", "games", "rooms", "audit", "softDeleted", "files", "report"]

TAG_FUNC_MAP = {
    "messages": cleanMessages,
    "games": cleanGames,
    "rooms": cleanRooms,
    "audit": cleanAuditLog,
    "softDeleted": cleanSoftDeleted,
    "files": cleanOrphanFiles,
}


def parseArgs(argv):
    opt = {
        "apply": False,
        "only": "",
        "batchSize": BATCH_SIZE,
        "maxBatches": MAX_BATCHES,
    }
    for item in argv:
        if item == "--apply":
            opt["apply"] = True
        elif item == "--dry-run":
            opt["apply"] = False
        elif item.startswith("--only="):
            opt["only"] = item.split("=", 1)[1]
        elif item.startswith("--batch-size="):
            opt["batchSize"] = int(item.split("=", 1)[1])
        elif item.startswith("--max-batches="):
            opt["maxBatches"] = int(item.split("=", 1)[1])
        elif item in ("-h", "--help"):
            print(_USAGE)
            return None
        else:
            print(f"参数错误:{item}")
            return None
    return opt


def main(argv=None):
    global BATCH_SIZE
    global MAX_BATCHES

    argv = argv if argv is not None else sys.argv[1:]
    opt = parseArgs(argv)
    if opt is None:
        return 2

    BATCH_SIZE = max(1, opt["batchSize"])
    MAX_BATCHES = max(1, opt["maxBatches"])

    onlySet = set()
    if opt["only"]:
        onlySet = {item.strip() for item in opt["only"].split(",") if item.strip()}
        unknown = onlySet - set(TAG_ORDER)
        if unknown:
            print(f"未知 tag:{unknown}, 可用:{TAG_ORDER}")
            return 2

    _LOG.info("B: dataClean begin, version:%s, apply:%s, batchSize:%s, maxBatches:%s",
              _VERSION, opt["apply"], BATCH_SIZE, MAX_BATCHES)
    if not opt["apply"]:
        _LOG.info("dry-run: 只统计候选条数, 不删除")

    failedTagList = []
    conn = None
    try:
        conn, dbName = connectDB()
        _LOG.info("connected db:%s", dbName)

        for tag in TAG_ORDER:
            if onlySet and tag not in onlySet:
                continue
            if tag == "report":
                try:
                    reportTables(conn, dbName)
                except Exception as e:
                    failedTagList.append(tag)
                    _LOG.error(f"[{tag}] failed:{e}")
                continue

            func = TAG_FUNC_MAP.get(tag)
            if not func:
                continue
            begin = time.time()
            try:
                func(conn, dbName, opt["apply"])
            except Exception as e:
                failedTagList.append(tag)
                _LOG.error(f"[{tag}] failed after {time.time() - begin:.1f}s:{e}")
            time.sleep(0.05)

    except Exception as e:
        _LOG.error(f"dataClean fatal:{e}")
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    deletedTotal = sum(item["deleted"] for item in _statList)
    _LOG.info("SUMMARY deleted_total:%s, failed_tags:%s, apply:%s",
              deletedTotal, failedTagList or "none", opt["apply"])
    _LOG.info("E: dataClean end")

    return 0 if not failedTagList else 1

#主流程 end


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    sys.exit(main())
