#!/usr/bin/env bash
# 家庭麻将 · 回滚脚本
#
# 用法：
#   sudo bash rollback.sh <备份时间戳>             # 只回退代码（推荐，库结构不变）
#   sudo bash rollback.sh <备份时间戳> --with-db   # 代码 + 库一起恢复（破坏性，需停服）
#   sudo bash rollback.sh --skin-off               # 只关皮肤功能（.env 开关，最快）
#   sudo bash rollback.sh --skin-on
#
# 备份文件由 deploy.sh 生成：
#   /data/backup/mahjong_data_<ts>.sql
#   /data/backup/majiang_src_<ts>.tgz
#   /data/backup/majiangapp_<ts>.tgz
set -euo pipefail

BACKUP_DIR=/data/backup
APP_DIR=/data/majiang/src
WEB_DIR=/data/webserver/majiangapp
SERVICE=mahjong

log() { printf '\n== %s\n' "$*"; }

setSkinFlag() {
  local value=$1
  log "皮肤开关 SKIN_ENABLED=$value"
  if grep -q '^SKIN_ENABLED=' "$APP_DIR/.env"; then
    sed -i "s/^SKIN_ENABLED=.*/SKIN_ENABLED=$value/" "$APP_DIR/.env"
  else
    printf '\nSKIN_ENABLED=%s\n' "$value" >> "$APP_DIR/.env"
  fi
  systemctl restart "$SERVICE"
  sleep 2
  systemctl is-active "$SERVICE"
  curl -fsS -m 5 http://127.0.0.1:8000/api/health; echo
}

case "${1:-}" in
  --skin-off) setSkinFlag false; exit 0 ;;
  --skin-on)  setSkinFlag true;  exit 0 ;;
esac

STAMP=${1:?用法: rollback.sh <备份时间戳> [--with-db]}
DB_ROLLBACK=${2:-}

[ -f "$BACKUP_DIR/majiang_src_$STAMP.tgz" ] || { echo "找不到 $BACKUP_DIR/majiang_src_$STAMP.tgz"; exit 1; }

if [ "$DB_ROLLBACK" = "--with-db" ]; then
  [ -f "$BACKUP_DIR/mahjong_data_$STAMP.sql" ] || { echo "找不到库备份"; exit 1; }
  log "停服"
  systemctl stop "$SERVICE"
  log "恢复数据库（先备份当前库）"
  set -a; . "$APP_DIR/.env"; set +a
  mysqldump -h"${MYSQL_WRITE_HOST:-127.0.0.1}" -P"${MYSQL_WRITE_PORT:-3306}" \
    -u"${MYSQL_WRITE_USER}" -p"${MYSQL_WRITE_PASSWD}" --single-transaction --routines --no-tablespaces \
    "${MYSQL_WRITE_DB:-mahjong_data}" > "$BACKUP_DIR/mahjong_data_pre_rollback_$(date +%Y%m%d_%H%M%S).sql"
  mysql -h"${MYSQL_WRITE_HOST:-127.0.0.1}" -P"${MYSQL_WRITE_PORT:-3306}" \
    -u"${MYSQL_WRITE_USER}" -p"${MYSQL_WRITE_PASSWD}" \
    "${MYSQL_WRITE_DB:-mahjong_data}" < "$BACKUP_DIR/mahjong_data_$STAMP.sql"
fi

log "回退后端代码"
rm -rf /tmp/mj_rollback && mkdir -p /tmp/mj_rollback/src /tmp/mj_rollback/web
tar xzf "$BACKUP_DIR/majiang_src_$STAMP.tgz" -C /tmp/mj_rollback
rsync -a --delete --exclude '.env' --exclude '__pycache__/' /tmp/mj_rollback/src/ "$APP_DIR/"

log "回退前端产物"
if [ -f "$BACKUP_DIR/majiangapp_$STAMP.tgz" ]; then
  tar xzf "$BACKUP_DIR/majiangapp_$STAMP.tgz" -C /tmp/mj_rollback/web
  rsync -a --delete --exclude 'tiles/' /tmp/mj_rollback/web/majiangapp/ "$WEB_DIR/"
fi

chown -R majiang:majiang "$APP_DIR" "$WEB_DIR"
chmod -R a+rX "$WEB_DIR"

log "启动"
systemctl start "$SERVICE"
sleep 2
systemctl is-active "$SERVICE"
curl -fsS -m 5 http://127.0.0.1:8000/api/health; echo
echo "OK  已回退到 $STAMP"
