#!/bin/bash
# 发版前状态巡检：当前版本 / 健康 / 房间分布 / 服务状态。
# 用法（生产）：scp 到 ~/mj_deploy2/ 后 `sudo bash check_state.sh`
set -u

cd /data/majiang/src || exit 1

echo "== 后端版本 =="
grep -n '^VERSION' config/basicSettings.py

echo "== 健康 =="
curl -s http://127.0.0.1:8000/api/health
echo

echo "== 房间状态分布 =="
mysql -umjapp -pREDACTED_DB_PASSWORD mahjong_data -N \
  -e "select roomStatus, count(*) from mj_room where delFlag=0 group by roomStatus;" 2>/dev/null

echo "== 进行中对局（gameStatus=PLAYING）=="
mysql -umjapp -pREDACTED_DB_PASSWORD mahjong_data -N \
  -e "select recID, roomID, gameStatus from mj_game where gameStatus='PLAYING' limit 10;" 2>/dev/null

echo "== 服务 =="
systemctl is-active mahjong
echo "== 前端入口指纹（index.html / mobile.html 实际引用）=="
grep -o 'src="[^"]*"' /data/webserver/majiangapp/index.html | head -2
grep -o 'src="[^"]*"' /data/webserver/mjmobile/mobile.html | head -2
ls -l --time-style=+%m-%d\ %H:%M /data/webserver/majiangapp/index.html /data/webserver/mjmobile/mobile.html
