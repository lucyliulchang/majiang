#!/bin/bash
# 生产端房间/对局状态巡检（只读）。用法：sudo bash 50_rooms_state.sh
set -u
if [ -r /data/majiang/src/.env ]; then set -a; . /data/majiang/src/.env; set +a; fi
M=(mysql -h"${MYSQL_WRITE_HOST:-127.0.0.1}" -P"${MYSQL_WRITE_PORT:-3306}" -u"${MYSQL_WRITE_USER:-mjapp}" -p"${MYSQL_WRITE_PASSWD:-}" "${MYSQL_WRITE_DB:-mahjong_data}")

echo "== 房间状态分布（delFlag=0）=="
"${M[@]}" -t -e "select roomStatus, count(*) as cnt from mj_room where delFlag=0 group by roomStatus;" 2>/dev/null

echo
echo "== 对局状态分布 =="
"${M[@]}" -t -e "select gameStatus, count(*) as cnt from mj_game group by gameStatus;" 2>/dev/null

echo
echo "== OPEN 房间明细 =="
"${M[@]}" -t -e "select recID, roomCode, roomName, roomStatus, ownerUserID, createdYMDHMS, closedYMDHMS from mj_room where delFlag=0 and roomStatus='OPEN' order by recID;" 2>/dev/null

echo
echo "== PLAYING 对局明细 =="
"${M[@]}" -t -e "select g.recID, g.roomID, g.gameStatus, g.createdYMDHMS, r.roomCode, r.roomStatus, r.delFlag from mj_game g left join mj_room r on r.recID=g.roomID where g.gameStatus='PLAYING' order by g.recID;" 2>/dev/null

echo
echo "== 各 OPEN 房间的玩家占用 =="
"${M[@]}" -t -e "select r.recID as roomID, r.roomCode, count(gp.recID) as players from mj_room r left join mj_game g on g.roomID=r.recID left join mj_game_player gp on gp.gameID=g.recID where r.delFlag=0 and r.roomStatus='OPEN' group by r.recID, r.roomCode order by r.recID;" 2>/dev/null
