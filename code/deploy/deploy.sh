#!/usr/bin/env bash
# 家庭麻将 · 发版脚本（在目标服务器本机执行，路径见下方变量）
#
# 用法： sudo bash deploy.sh <发布包目录>
#   发布包结构：
#     <pkg>/backend/    ← code/backend/src 的全部内容（不含 .env）
#     <pkg>/dist/       ← code/frontend/dist 的全部内容
#
# 顺序：备份 → 同步代码 → 修权限 → 重启 → 健康检查
# 任何一步失败立即退出（set -e），不会留下半套代码。
set -euo pipefail

PKG=${1:?用法: deploy.sh <发布包目录>}
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/data/backup
APP_DIR=/data/majiang/src
WEB_DIR=/data/webserver/majiangapp
SERVICE=mahjong

log() { printf '\n== %s\n' "$*"; }

[ -d "$PKG/backend" ] || { echo "缺少 $PKG/backend"; exit 1; }
[ -d "$PKG/dist" ] || { echo "缺少 $PKG/dist"; exit 1; }
[ -f "$APP_DIR/.env" ] || { echo "缺少 $APP_DIR/.env，先按 .env.example 生成"; exit 1; }

# ---------- 1) 备份（库 + 代码 + 前端产物）----------
log "备份到 $BACKUP_DIR（时间戳 $STAMP）"
mkdir -p "$BACKUP_DIR"
set -a
# shellcheck disable=SC1090
. "$APP_DIR/.env"
set +a
mysqldump -h"${MYSQL_WRITE_HOST:-127.0.0.1}" -P"${MYSQL_WRITE_PORT:-3306}" \
  -u"${MYSQL_WRITE_USER}" -p"${MYSQL_WRITE_PASSWD}" \
  --single-transaction --routines --no-tablespaces \
  "${MYSQL_WRITE_DB:-mahjong_data}" > "$BACKUP_DIR/mahjong_data_$STAMP.sql"
tar czf "$BACKUP_DIR/majiang_src_$STAMP.tgz" -C /data/majiang src
tar czf "$BACKUP_DIR/majiangapp_$STAMP.tgz" -C /data/webserver majiangapp
ls -lh "$BACKUP_DIR" | tail -3

# ---------- 2) 同步后端（--delete 只清代码树，.env 必须排除）----------
log "同步后端 -> $APP_DIR"
rsync -a --delete \
  --exclude '.env' --exclude '__pycache__/' --exclude '.venv/' \
  "$PKG/backend/" "$APP_DIR/"

# ---------- 3) 同步前端（tiles/ 是运行期图片，必须排除）----------
log "同步前端 -> $WEB_DIR"
mkdir -p "$WEB_DIR/tiles"
rsync -a --delete --exclude 'tiles/' "$PKG/dist/" "$WEB_DIR/"

chown -R majiang:majiang "$APP_DIR" "$WEB_DIR"
chown -R majiang:majiang /data/majiang/log /data/majiang/data
chmod -R a+rX "$WEB_DIR"

# ---------- 4) 重启 ----------
log "重启 $SERVICE"
systemctl daemon-reload
systemctl restart "$SERVICE"
sleep 2
systemctl is-active "$SERVICE"

# ---------- 5) 健康检查（uvicorn 冷启动约 5 秒，轮询最多 30 秒）----------
log "健康检查"
for _ in $(seq 1 30); do
  if curl -fsS -m 2 http://127.0.0.1:8000/api/health; then
    echo
    echo "OK  回滚点： $STAMP  （sudo bash rollback.sh $STAMP）"
    exit 0
  fi
  sleep 1
done
echo '健康检查失败'
systemctl status "$SERVICE" --no-pager -l | tail -20
exit 1
