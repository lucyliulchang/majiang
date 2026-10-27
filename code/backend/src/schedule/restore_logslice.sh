#!/usr/bin/env bash
#Filename: restore_logslice.sh
#Description: 定时日志切片入口(crontab 00:00 拉起)
#             切分的是 crontab 重定向产生的 /data/majiang/log/schedule/*.log,
#             应用自身日志走 journald, 不在此处理
set -euo pipefail

WORKING_DIR=${MAHJONG_HOME:-/data/majiang/src}

cd "${WORKING_DIR}"

exec /bin/bash schedule/logslice.sh "$@"
