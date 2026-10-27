#!/usr/bin/env bash
#Filename: restore_monitor.sh
#Description: 进程/接口/文件变更监控入口(crontab 每 5 分钟拉起)
#             monitor.py 是一次性脚本, 跑完即退, 不需要先 kill 旧进程;
#             flock 防止上一轮未结束时重入
set -euo pipefail

WORKING_DIR=${MAHJONG_HOME:-/data/majiang/src}
pythonApp=${MAHJONG_PYTHON:-/data/userbin/python3/bin/python3}
application=monitor.py

cd "${WORKING_DIR}/monitor"

exec flock -n /tmp/mahjong-monitor.lock "${pythonApp}" "${application}" "$@"
