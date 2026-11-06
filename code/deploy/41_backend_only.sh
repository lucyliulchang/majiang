#!/usr/bin/env bash
# v1.1.3 发布（仅后端 · 连6 补齐 345678；前端不重建、不动 dist、不做冒烟）
# 用法：sudo bash 41_backend_only.sh  （预先 scp backend.tar.gz 到 /home/<部署用户>/mj_deploy2/）
# 部署用户与对外域名按环境注入，仓库里只放示例值：export MJ_DEPLOY_USER=... MJ_PUBLIC_BASE_URL=...
set -uo pipefail
MJ_DEPLOY_USER="${MJ_DEPLOY_USER:-deployer}"
MJ_PUBLIC_BASE_URL="${MJ_PUBLIC_BASE_URL:-https://www.test.com}"
set -a; . /data/majiang/src/.env; set +a
DB="${MYSQL_WRITE_DB:-mahjong_data}"
M=(mysql -h"${MYSQL_WRITE_HOST:-127.0.0.1}" -P"${MYSQL_WRITE_PORT:-3306}" -u"${MYSQL_WRITE_USER:-mjapp}" -p"${MYSQL_WRITE_PASSWD}" "$DB")
PKG="/home/${MJ_DEPLOY_USER}/mj_deploy2"
APP_DIR=/data/majiang/src
BACKUP_DIR=/data/backup
STAMP=$(date +%Y%m%d_%H%M%S)

echo "== 发布前现状（仅记录，用户已授权中断）"
"${M[@]}" -t -e "SELECT recID, roomCode, roomStatus FROM mj_room WHERE roomStatus='OPEN'" 2>/dev/null
"${M[@]}" -t -e "SELECT recID, roomID, gameStatus FROM mj_game WHERE gameStatus='PLAYING'" 2>/dev/null
OPEN=$( "${M[@]}" -N -B -e "SELECT COUNT(*) FROM mj_room WHERE roomStatus='OPEN'" 2>/dev/null )
PLAY=$( "${M[@]}" -N -B -e "SELECT COUNT(*) FROM mj_game WHERE gameStatus='PLAYING'" 2>/dev/null )
echo "OPEN 房=${OPEN}  PLAYING 场次=${PLAY}（将被中断）"

echo
echo "==================== 1) 备份后端"
tar czf "$BACKUP_DIR/majiang_src_${STAMP}.tgz" -C /data/majiang src
chmod 600 "$BACKUP_DIR/majiang_src_${STAMP}.tgz"
ls -lh "$BACKUP_DIR/majiang_src_${STAMP}.tgz"

echo
echo "==================== 2) 同步后端（排 .env / 缓存）"
rm -rf /tmp/mj_backend && mkdir -p /tmp/mj_backend
tar xzf "$PKG/backend.tar.gz" -C /tmp/mj_backend
rsync -a --delete --exclude '.env' --exclude '__pycache__/' --exclude '.pytest_cache/' \
  /tmp/mj_backend/ "$APP_DIR/"
chown -R majiang:majiang "$APP_DIR"
chown -R majiang:majiang /data/majiang/log /data/majiang/data
ls -l "$APP_DIR/.env"
grep -n 'VERSION =' "$APP_DIR/config/basicSettings.py"
grep -n 'for low, high in' "$APP_DIR/game/families/baishi/fan.py"

echo
echo "==================== 3) 依赖（requirements 未变时秒过）"
cd "$APP_DIR"
sudo -n -u majiang /data/majiang/venv/bin/pip install --disable-pip-version-check -q -r requirements.txt

echo
echo "==================== 4) 重启 mahjong"
systemctl restart mahjong
for _ in $(seq 1 40); do
  if curl -fsS -m 2 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "health: $(curl -sS http://127.0.0.1:8000/api/health)"
    systemctl is-active mahjong
    break
  fi
  sleep 1
done

echo
echo "==================== 5) 启动日志"
journalctl -u mahjong -n 12 --no-pager --output=cat

echo
echo "==================== 6) 只读核对（不做冒烟）"
date
echo -n "health(本机): "; curl -sS -m 3 http://127.0.0.1:8000/api/health; echo
echo -n "health(对外): "; curl -sS -m 5 "${MJ_PUBLIC_BASE_URL}/majiangapi/health"; echo
echo -n "服务状态: "; systemctl is-active mahjong
"${M[@]}" -N -B -e "SELECT CONCAT('baishi_default fan_table 项数=', JSON_LENGTH(JSON_EXTRACT(configJson,'\$.fan_table'))) FROM mj_rule_template WHERE templateCode='baishi_default'" 2>/dev/null
"${M[@]}" -N -B -e "SELECT CONCAT('OPEN 房数=', COUNT(*)) FROM mj_room WHERE roomStatus='OPEN'" 2>/dev/null
"${M[@]}" -N -B -e "SELECT CONCAT('PLAYING 场次=', COUNT(*)) FROM mj_game WHERE gameStatus='PLAYING'" 2>/dev/null
echo -n "前端入口(应保持不变): "; grep -o 'assets/index-[a-zA-Z0-9._-]*' /data/webserver/majiangapp/index.html | head -1
echo -n "手机入口(应保持不变): "; grep -o 'assets/mobile-[a-zA-Z0-9._-]*' /data/webserver/mjmobile/mobile.html | head -1

echo
echo "== 最新备份"
ls -lht /data/backup | head -5
echo "回滚点： $STAMP"
