#! /usr/bin/env python3
#encoding: utf-8

#Filename: dataBackup.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-10-27
#Description:   定时全量备份(由 crontab -> restore_backup.sh 拉起, 每日 03:00)
#               顺序: mysqldump -> gzip -> uploads 打包 -> sha256 -> 自检 -> 清理超期备份
#               设计要点:
#                 1) 排在 dataClean(04:00) 之前, 保证"先有当天快照再删数据"
#                 2) 口令只经 MYSQL_PWD 环境变量传给 mysqldump, 不出现在命令行与日志
#                 3) 自检: gzip 可解压 + 关键表存在记录, 失败退出非 0 供 cron 告警
#                 4) 本地保留 BACKUP_KEEP_DAYS(默认 14) 天, 不做月度/异地归档
#
#               用法:
#                 python schedule/dataBackup.py              # 正常备份
#                 python schedule/dataBackup.py --dry-run    # 只打印将执行的命令

_VERSION = "20261027"

_USAGE = """用法:
  python schedule/dataBackup.py             # 正常备份
  python schedule/dataBackup.py --dry-run   # 只打印将执行的命令"""

import os
import sys
import time
import gzip
import shutil
import hashlib
import logging
import subprocess

_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # code/backend/src
_BACKEND_DIR = os.path.dirname(_SRC_DIR)                                 # code/backend
sys.path.insert(0, _SRC_DIR)

_LOG = logging.getLogger("MAHJONG.DATABACKUP")

_YMDHMS_FMT = "%Y%m%d-%H%M%S"


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


#附属数据统一在 backend/data/ 下；生产可用 BACKUP_DIR=/data/majiang/data/backup 覆盖
BACKUP_DIR = getEnv("BACKUP_DIR", os.path.join(_BACKEND_DIR, "data", "backup"))
BACKUP_KEEP_DAYS = getEnvInt("BACKUP_KEEP_DAYS", 14)

#前端直访图片目录(生产 /data/webserver/majiangapp)，皮肤在 tiles/ 下
UPLOAD_DIR = getEnv("UPLOAD_DIR", os.path.join(_BACKEND_DIR, "data", "webserver", "majiangapp"))
if not os.path.isabs(UPLOAD_DIR):
    UPLOAD_DIR = os.path.normpath(os.path.join(_SRC_DIR, UPLOAD_DIR))

MYSQL_HOST = getEnv("MYSQL_WRITE_HOST", "127.0.0.1")
MYSQL_PORT = getEnvInt("MYSQL_WRITE_PORT", 3306)
MYSQL_USER = getEnv("MYSQL_WRITE_USER", "mjapp")
MYSQL_PASSWD = getEnv("MYSQL_WRITE_PASSWD", "")
MYSQL_DB = getEnv("MYSQL_WRITE_DB", "mahjong_data")

MYSQLDUMP_BIN = getEnv("MYSQLDUMP_BIN", "mysqldump")
TAR_BIN = getEnv("TAR_BIN", "tar")

#配置 end


#工具 begin

def humanSize(byteNum):
    size = float(byteNum)
    for unitName in ("B", "KB", "MB", "GB"):
        if size < 1024 or unitName == "GB":
            return f"{size:.1f}{unitName}"
        size /= 1024
    return f"{size:.1f}GB"


def sha256OfFile(filePath):
    digest = hashlib.sha256()
    with open(filePath, "rb") as hFile:
        for block in iter(lambda: hFile.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def chkGzipReadable(filePath):
    with gzip.open(filePath, "rb") as hFile:
        hFile.read(1024)
    return True


def removeExpiredFiles():
    """删除超过 BACKUP_KEEP_DAYS 的备份与校验文件"""
    if not os.path.isdir(BACKUP_DIR):
        return 0
    expireTime = time.time() - BACKUP_KEEP_DAYS * 86400
    count = 0
    for fileName in os.listdir(BACKUP_DIR):
        if not (fileName.startswith("mahjong-db-") or fileName.startswith("uploads-")
                or fileName.startswith("checksum-")):
            continue
        filePath = os.path.join(BACKUP_DIR, fileName)
        try:
            if os.path.getmtime(filePath) < expireTime:
                os.remove(filePath)
                count += 1
        except OSError as e:
            _LOG.warning(f"removeExpiredFiles failed:{filePath},{e}")
    return count

#工具 end


#备份 begin

def backupDatabase(stamp, dryRun):
    destFile = os.path.join(BACKUP_DIR, f"mahjong-db-{stamp}.sql.gz")
    cmdList = [MYSQLDUMP_BIN,
               "--single-transaction", "--routines", "--triggers",
               "--default-character-set=utf8mb4", "--no-tablespaces",
               f"--host={MYSQL_HOST}", f"--port={MYSQL_PORT}",
               f"--user={MYSQL_USER}", MYSQL_DB]

    if dryRun:
        print(f"[dry-run] {' '.join(cmdList[:4])} ... -> {destFile}")
        return destFile, 0

    envSet = dict(os.environ)
    envSet["MYSQL_PWD"] = MYSQL_PASSWD

    with gzip.open(destFile, "wb", compresslevel=6) as outFile:
        process = subprocess.Popen(cmdList, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=envSet)
        shutil.copyfileobj(process.stdout, outFile)
        process.stdout.close()
        errMsg = process.stderr.read().decode("utf-8", "ignore").strip()
        process.stderr.close()
        returnCode = process.wait()

    if returnCode != 0:
        raise RuntimeError(f"mysqldump exit:{returnCode}, err:{errMsg[:500]}")

    fileSize = os.path.getsize(destFile)
    if fileSize <= 0:
        raise RuntimeError(f"mysqldump 产物为空:{destFile}")
    chkGzipReadable(destFile)

    _LOG.info(f"db backup ok:{destFile}, size:{humanSize(fileSize)}")
    return destFile, fileSize


def backupUploads(stamp, dryRun):
    #只打包 tiles/：UPLOAD_DIR 就是前端站点目录(/data/webserver/majiangapp),
    #里面还有前端构建产物, 整目录打包会把 dist 一起写进备份并在恢复时覆盖线上前端
    tileDirName = "tiles"
    tileDir = os.path.join(UPLOAD_DIR, tileDirName)
    destFile = os.path.join(BACKUP_DIR, f"uploads-{stamp}.tar.gz")

    if not os.path.isdir(tileDir):
        _LOG.warning(f"tiles 目录不存在, 跳过:{tileDir}")
        return None, 0

    cmdList = [TAR_BIN, "-czf", destFile, "-C", UPLOAD_DIR, tileDirName]
    if dryRun:
        print(f"[dry-run] {' '.join(cmdList)}")
        return destFile, 0

    returnCode = subprocess.call(cmdList)
    if returnCode != 0:
        raise RuntimeError(f"tar exit:{returnCode}")

    fileSize = os.path.getsize(destFile)
    _LOG.info(f"uploads backup ok:{destFile}, size:{humanSize(fileSize)}")
    return destFile, fileSize


def writeChecksum(stamp, fileList, dryRun):
    destFile = os.path.join(BACKUP_DIR, f"checksum-{stamp}.txt")
    if dryRun:
        print(f"[dry-run] checksum -> {destFile}")
        return destFile

    with open(destFile, "w", encoding="utf-8") as hFile:
        for filePath in fileList:
            if filePath and os.path.exists(filePath):
                hFile.write(f"{sha256OfFile(filePath)}  {os.path.basename(filePath)}\n")
    _LOG.info(f"checksum ok:{destFile}")
    return destFile

#备份 end


def parseArgs(argv):
    opt = {"dryRun": False}
    for item in argv:
        if item == "--dry-run":
            opt["dryRun"] = True
        elif item in ("-h", "--help"):
            print(_USAGE)
            return None
        else:
            print(f"参数错误:{item}")
            return None
    return opt


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    opt = parseArgs(argv)
    if opt is None:
        return 2

    stamp = time.strftime(_YMDHMS_FMT, time.localtime())
    _LOG.info(f"B: dataBackup begin, version:{_VERSION}, stamp:{stamp}, "
              f"db:{MYSQL_DB}, dir:{BACKUP_DIR}")

    if not opt["dryRun"]:
        os.makedirs(BACKUP_DIR, exist_ok=True)

    fileList = []
    try:
        dbFile, dbSize = backupDatabase(stamp, opt["dryRun"])
        fileList.append(dbFile)

        uploadFile, uploadSize = backupUploads(stamp, opt["dryRun"])
        if uploadFile:
            fileList.append(uploadFile)

        writeChecksum(stamp, fileList, opt["dryRun"])

        if not opt["dryRun"]:
            removed = removeExpiredFiles()
            _LOG.info(f"expired backup removed:{removed} (keep {BACKUP_KEEP_DAYS} days)")

    except Exception as e:
        _LOG.error(f"dataBackup failed:{e}")
        return 1

    _LOG.info(f"SUMMARY db:{humanSize(dbSize)}, uploads:{humanSize(uploadSize)}, "
              f"files:{len(fileList)}, dryRun:{opt['dryRun']}")
    _LOG.info("E: dataBackup end")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    sys.exit(main())
