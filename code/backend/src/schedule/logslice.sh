#!/usr/bin/env bash
#Filename: logslice.sh
#Description: 每日 00:00 由 restore_logslice.sh 调用
#             1) 把 schedule 日志按"前一天日期"落到 backup 目录并截断原文件
#             2) 删除 30 天前的切片
#             nginx/journald/慢查询日志由各自轮转管理, 不在此处理
set -euo pipefail

logSourceDir=${MAHJONG_LOG_DIR:-/data/majiang/log/schedule}
logBackupDir=${logSourceDir}/backup
keepDays=${MAHJONG_LOG_KEEP_DAYS:-30}

lastDay=`/bin/date -d last-day +%Y%m%d`

/bin/mkdir -p "${logBackupDir}"

for filePath in "${logSourceDir}"/*.log; do
    [ -e "${filePath}" ] || continue
    fileName=`/bin/basename "${filePath}" .log`
    /bin/cp "${filePath}" "${logBackupDir}/${fileName}-${lastDay}.log"
    /bin/echo '' > "${filePath}"
done

#清理超期切片
/usr/bin/find "${logBackupDir}" -name '*.log' -type f -mtime +${keepDays} -delete

#日志文件自身不存在时 mkdir/cp 会失败, 这里不做兜底 swallow, 由 set -e 暴露给 cron
