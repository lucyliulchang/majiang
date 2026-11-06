#!/bin/bash
# 发版前状态巡检：当前版本 / 健康 / 房间分布 / 服务状态。
# 用法（生产）：scp 到 ~/mj_deploy2/ 后 `sudo bash check_state.sh`
set -u

cd /data/majiang/src || exit 1

# 数据库连接只从服务器上的 .env 读取（口令不写死在脚本里、不入库）
if [ -r /data/majiang/src/.env ]; then set -a; . /data/majiang/src/.env; set +a; fi
M=(mysql -h"${MYSQL_WRITE_HOST:-127.0.0.1}" -P"${MYSQL_WRITE_PORT:-3306}" -u"${MYSQL_WRITE_USER:-mjapp}" -p"${MYSQL_WRITE_PASSWD:-}" "${MYSQL_WRITE_DB:-mahjong_data}")

echo "== 后端版本 =="
grep -n '^VERSION' config/basicSettings.py

echo "== 健康 =="
curl -s http://127.0.0.1:8000/api/health
echo

echo "== 房间状态分布 =="
"${M[@]}" -N \
  -e "select roomStatus, count(*) from mj_room where delFlag=0 group by roomStatus;" 2>/dev/null

echo "== 进行中对局（gameStatus=PLAYING）=="
"${M[@]}" -N \
  -e "select recID, roomID, gameStatus from mj_game where gameStatus='PLAYING' limit 10;" 2>/dev/null

echo "== 服务 =="
systemctl is-active mahjong
echo "== 前端入口指纹（index.html / mobile.html 实际引用）=="
grep -o 'src="[^"]*"' /data/webserver/majiangapp/index.html | head -2
grep -o 'src="[^"]*"' /data/webserver/mjmobile/mobile.html | head -2
ls -l --time-style=+%m-%d\ %H:%M /data/webserver/majiangapp/index.html /data/webserver/mjmobile/mobile.html
