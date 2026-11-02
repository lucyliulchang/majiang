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

echo "== 房间状态分布（deletedAt is null）=="
mysql -umjapp -pREDACTED_DB_PASSWORD mahjong_data -N \
  -e "select roomStatus, count(*) from mj_room where deletedAt is null group by roomStatus;" 2>/dev/null

echo "== 进行中对局（PLAYING）=="
mysql -umjapp -pREDACTED_DB_PASSWORD mahjong_data -N \
  -e "select roomID, roomCode, hostLoginID, updatedYMDHMS from mj_room where roomStatus='PLAYING' and deletedAt is null;" 2>/dev/null

echo "== 服务 =="
systemctl is-active mahjong
echo "== 前端入口指纹 =="
ls -1 /data/webserver/majiangapp/assets/index-*.js 2>/dev/null | tail -2
ls -1 /data/webserver/mjmobile/assets/mobile-*.js 2>/dev/null | tail -2
