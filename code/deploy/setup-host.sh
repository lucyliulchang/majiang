#!/usr/bin/env bash
# 首次装机的幂等脚本，只做「用户 / 目录 / 依赖 / systemd / nginx」
# 用法： sudo bash setup-host.sh [/tmp/mj_pkg]
# 代码与前端产物的每次发布走 deploy.sh。
set -euo pipefail

PKG=${1:-/tmp/mj_pkg}
APP_DIR=/data/majiang/src
WEB_DIR=/data/webserver/majiangapp

log() { printf '\n== %s\n' "$*"; }

log "用户与目录"
id majiang >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin majiang
mkdir -p "$APP_DIR" /data/majiang/log/schedule \
         /data/majiang/data/db /data/majiang/data/test /data/majiang/data/backup \
         "$WEB_DIR/tiles"

log "Python 依赖"
python3 -m pip install --quiet -r "$PKG/backend/requirements.txt" 2>&1 | tail -3 || true
python3 -c 'import fastapi, uvicorn, pymysql, dbutils, pydantic_settings, jwt, multipart, requests; print("deps ok")'

log "systemd 单元"
install -m 644 "$PKG/mahjong.service" /etc/systemd/system/mahjong.service
systemctl daemon-reload
systemctl enable mahjong >/dev/null 2>&1 || true

log "nginx 片段（首次需要人工确认插入位置，避免误改共享配置）"
ls -l /tmp/mj_pkg/nginx-majiang.conf

log "完成：把 .env 放到 $APP_DIR/.env（600），再 bash $PKG/deploy.sh $PKG"
