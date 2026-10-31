#!/usr/bin/env bash
# 数据清理（一次性）：删除 v1.1.0 发版冒烟产生的机器人牌桌及其场次/局/参与者/聊天记录。
#
# 安全边界（硬约束）：
#   - 只删 roomName 匹配 'v1.1.0 冒烟%' 的房间（发版冒烟专用房名），真人房间一律不动；
#   - 可用 ROOM_IDS=1,2,3 显式指定房间号白名单（优先级更高）；
#   - 先 mysqldump 备份 mj_room / mj_game / mj_game_player / mj_game_round / mj_room_message；
#   - 先演练（DRY_RUN=1，默认）打印待删行，确认后 DRY_RUN=0 落库；
#   - 无 DDL、不改表结构。
#
# 用法：
#   sudo DRY_RUN=1 bash 15_cleanup_smoke_rooms.sh
#   sudo DRY_RUN=0 bash 15_cleanup_smoke_rooms.sh
#   sudo DRY_RUN=0 ROOM_IDS=9,10 bash 15_cleanup_smoke_rooms.sh
#
# 回滚：
#   mysql mahjong_data < /data/backup/smoke_rooms_<STAMP>.sql
set -euo pipefail

DB="${DB:-mahjong_data}"
BACKUP_DIR="${BACKUP_DIR:-/data/backup}"
NAME_PATTERN="${NAME_PATTERN:-v1.1.0 冒烟%}"
ROOM_IDS="${ROOM_IDS:-}"
DRY_RUN="${DRY_RUN:-1}"
STAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/smoke_rooms_${STAMP}.sql"

echo "== 备份 5 张表 -> $BACKUP_FILE"
mysqldump --single-transaction --no-tablespaces "$DB" \
  mj_room mj_game mj_game_player mj_game_round mj_room_message > "$BACKUP_FILE"
ls -lh "$BACKUP_FILE"

if [ -n "$ROOM_IDS" ]; then
  IDS="$ROOM_IDS"
  echo "== 使用显式白名单：$IDS"
else
  IDS=$(mysql -N -B "$DB" -e "SELECT GROUP_CONCAT(recID) FROM mj_room WHERE roomName LIKE '${NAME_PATTERN}'")
  echo "== 按房名匹配 '${NAME_PATTERN}' 命中房间：${IDS:-（无）}"
fi

if [ -z "${IDS:-}" ]; then
  echo "没有待清理的房间，退出。"
  exit 0
fi

IN_LIST="($IDS)"

echo
echo "== 待删房间"
mysql -t "$DB" -e "SELECT recID, roomCode, roomName, roomStatus, createdYMDHMS FROM mj_room WHERE recID IN ${IN_LIST} ORDER BY recID"

GAMES=$(mysql -N -B "$DB" -e "SELECT GROUP_CONCAT(recID) FROM mj_game WHERE roomID IN ${IN_LIST}")
GAME_IN="($GAMES)"

echo
echo "== 影响行数统计"
for spec in "mj_game_round:gameID:${GAME_IN}" "mj_game_player:gameID:${GAME_IN}" "mj_room_message:roomID:${IN_LIST}" "mj_game:recID:${GAME_IN}" "mj_room:recID:${IN_LIST}"; do
  table="${spec%%:*}"; rest="${spec#*:}"; col="${rest%%:*}"; ids="${rest#*:}"
  count=$(mysql -N -B "$DB" -e "SELECT COUNT(*) FROM ${table} WHERE ${col} IN ${ids}" 2>/dev/null || echo "?")
  echo "   ${table}.${col}: ${count}"
done

if [ "$DRY_RUN" = "1" ]; then
  echo
  echo "== DRY_RUN=1：只演练，未落库。确认后执行：sudo DRY_RUN=0 bash $0"
  exit 0
fi

echo
echo "== 开始删除（先子表后主表）"
mysql "$DB" -e "
  DELETE FROM mj_game_round   WHERE gameID  IN ${GAME_IN};
  DELETE FROM mj_game_player  WHERE gameID  IN ${GAME_IN};
  DELETE FROM mj_room_message WHERE roomID  IN ${IN_LIST};
  DELETE FROM mj_game         WHERE recID   IN ${GAME_IN};
  DELETE FROM mj_room         WHERE recID   IN ${IN_LIST};
"

echo
echo "== 删除后校验"
mysql -t "$DB" -e "SELECT COUNT(*) AS remaining_smoke_rooms FROM mj_room WHERE recID IN ${IN_LIST}"
mysql -t "$DB" -e "SELECT COUNT(*) AS open_rooms FROM mj_room WHERE roomStatus='OPEN' AND (delFlag='0' OR delFlag IS NULL)"
echo
echo "== 回滚方式"
echo "   mysql ${DB} < ${BACKUP_FILE}"
