#!/usr/bin/env bash
# 数据修复（一次性）：清理生产遗留的「OPEN 幽灵房」（缺陷 B-1 的存量数据）
#
# 背景：自然打满一圈走的 _finish_game 从未写过 mj_room.roomStatus，于是 10/29、10/30 的
# 两桌（recID 4、5）场次已 FINISHED 却一直挂在大厅。代码已修（打满即落 CLOSED），
# 这里只补历史数据。
#
# 安全边界（硬约束）：
#   - 不加列、不改表结构，只写 roomStatus / closedYMDHMS / modifyID / modifyYMDHMS 四个字段；
#   - 只动白名单 recID（默认 4,5），且必须同时满足 roomStatus='OPEN' AND closedYMDHMS IS NULL，
#     已经修过的房不会被二次改写；
#   - 先 mysqldump 备份 mj_room，再演练（DRY_RUN=1，默认执行）确认影响行数。
#
# 用法：
#   sudo DRY_RUN=1 bash 14_close_stale_rooms.sh          # 只打印将影响哪些房（默认就是这个）
#   sudo DRY_RUN=0 bash 14_close_stale_rooms.sh          # 真正落库
#   sudo DRY_RUN=0 REC_IDS=4,5 EXPECTED=2 bash 14_close_stale_rooms.sh
#
# 回滚：
#   mysql mahjong_data < /data/backup/mj_room_<STAMP>.sql
#   （整表恢复；若期间已有新房间，改用脚本末尾打印的 UPDATE 反向语句逐条回滚）
set -euo pipefail

DB="${DB:-mahjong_data}"
BACKUP_DIR="${BACKUP_DIR:-/data/backup}"
REC_IDS="${REC_IDS:-4,5}"
EXPECTED="${EXPECTED:-2}"
DRY_RUN="${DRY_RUN:-1}"
STAMP=$(date +%Y%m%d_%H%M%S)
# 库时间口径：YYYYMMDDHHMMSS（见 common/miscCommon.getTime）
NOW=$(date +%Y%m%d%H%M%S)

WHERE="recID IN (${REC_IDS}) AND roomStatus = 'OPEN' AND closedYMDHMS IS NULL"

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/mj_room_${STAMP}.sql"

echo "== 备份 mj_room -> $BACKUP_FILE"
mysqldump --single-transaction --no-tablespaces "$DB" mj_room > "$BACKUP_FILE"
ls -lh "$BACKUP_FILE"

echo
echo "== 更新前的目标房间（白名单 ${REC_IDS}）"
mysql -t "$DB" -e "SELECT recID, roomCode, roomName, hostLoginID, roomStatus, closedYMDHMS, createdYMDHMS
  FROM mj_room WHERE recID IN (${REC_IDS}) ORDER BY recID"

BEFORE=$(mysql -N -B "$DB" -e "SELECT COUNT(*) FROM mj_room WHERE ${WHERE}")
echo "== 符合修复条件（OPEN 且 closedYMDHMS IS NULL）的房间数：${BEFORE}"

if [ "$DRY_RUN" = "1" ]; then
  echo
  echo "== DRY_RUN=1：只演练，未落库。确认无误后执行：sudo DRY_RUN=0 bash $0"
  exit 0
fi

AFFECTED=$(mysql -N -B "$DB" -e "UPDATE mj_room
  SET roomStatus = 'CLOSED',
      closedYMDHMS = '${NOW}',
      modifyID = 'ops',
      modifyYMDHMS = '${NOW}'
  WHERE ${WHERE};
  SELECT ROW_COUNT();")

echo
echo "== 影响行数：${AFFECTED}（期望 ${EXPECTED}）"
if [ "${AFFECTED}" != "${EXPECTED}" ]; then
  echo "!! 影响行数与期望不一致：可能已修复过，或白名单/条件不符，请人工核对后再决定是否收尾"
fi

echo
echo "== 更新后"
mysql -t "$DB" -e "SELECT recID, roomCode, roomName, roomStatus, closedYMDHMS, modifyID
  FROM mj_room WHERE recID IN (${REC_IDS}) ORDER BY recID"

echo
echo "== 剩余 OPEN 房（无人打牌时应为 0）"
mysql -t "$DB" -e "SELECT COUNT(*) AS openRooms FROM mj_room
  WHERE roomStatus = 'OPEN' AND (delFlag = '0' OR delFlag IS NULL)"

echo
echo "== 回滚方式"
echo "   整表恢复：mysql ${DB} < ${BACKUP_FILE}"
echo "   逐条反向：UPDATE mj_room SET roomStatus='OPEN', closedYMDHMS=NULL, modifyID='ops',"
echo "             modifyYMDHMS='${NOW}' WHERE recID IN (${REC_IDS});"
