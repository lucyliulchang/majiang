#!/usr/bin/env bash
#Filename: logslice.sh
#Description: 每日 00:00 由 restore_logslice.sh 调用(以 majiang 用户身份)
#             1) 把 log/schedule/*.log 按"前一天日期"落到 backup 目录并截断原文件
#             2) 清理 backup 目录中超过 keepDays 的切片
#             3) 清理 log 根目录下超过 keepDays 的滚动残留(mahjong.log.*)
#             注意: 绝不截断 log/mahjong.log —— 后端持句柄按 offset 写入,
#                   截断会产生文件空洞; 该文件由 RotatingFileHandler(10MB x 5) 自行滚动
#             nginx/journald/慢查询日志由各自轮转管理, 不在此处理
set -euo pipefail

logRootDir=${MAHJONG_LOG_DIR:-/data/majiang/log}
logSourceDir=${logRootDir}/schedule
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

#清理超期的 cron 切片
/usr/bin/find "${logBackupDir}" -maxdepth 1 -name '*.log' -type f -mtime +${keepDays} -delete

#清理应用日志的滚动残留(不含当前 mahjong.log 本身)
/usr/bin/find "${logRootDir}" -maxdepth 1 -type f -name 'mahjong.log.*' -mtime +${keepDays} -delete

#日志文件自身不存在时 mkdir/cp 会失败, 这里不做兜底 swallow, 由 set -e 暴露给 cron
