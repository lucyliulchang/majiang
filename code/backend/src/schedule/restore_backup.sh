#!/usr/bin/env bash
#Filename: restore_backup.sh
#Description: 定时全量备份入口(crontab 03:00 拉起)
#             必须在 restore_clean.sh(04:00) 之前执行, 保证先备份再清理
set -euo pipefail

WORKING_DIR=${MAHJONG_HOME:-/data/majiang/src}
pythonApp=${MAHJONG_PYTHON:-/data/userbin/python3/bin/python3}
application=schedule/dataBackup.py

cd "${WORKING_DIR}"

exec flock -n /tmp/mahjong-backup.lock "${pythonApp}" "${application}" "$@"
