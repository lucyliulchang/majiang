#!/usr/bin/env bash
#Filename: restore_clean.sh
#Description: 定时数据清理入口(crontab 04:00 拉起)
#             无参数=执行删除; 手工调试请显式传 --dry-run
#             路径按实际部署调整: MAHJONG_HOME / MAHJONG_PYTHON 可由环境变量覆盖
set -euo pipefail

WORKING_DIR=${MAHJONG_HOME:-/data/majiang/src}
pythonApp=${MAHJONG_PYTHON:-/data/userbin/python3/bin/python3}
application=schedule/dataClean.py

cd "${WORKING_DIR}"

if [ $# -eq 0 ]; then
    set -- --apply
fi

exec flock -n /tmp/mahjong-clean.lock "${pythonApp}" "${application}" "$@"
