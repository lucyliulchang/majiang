#!/usr/bin/env bash
# 迁移：mj_game_round 增列 finalHandsJson（终局四家手牌+副露，供战绩回放核对番种）
# 用法：sudo bash 13_add_final_hands.sh
set -euo pipefail

DB=mahjong_data
BACKUP_DIR=/data/backup
STAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "== 备份 mj_game_round -> $BACKUP_DIR/mj_game_round_$STAMP.sql"
mysqldump --single-transaction --no-tablespaces "$DB" mj_game_round > "$BACKUP_DIR/mj_game_round_$STAMP.sql"
ls -lh "$BACKUP_DIR/mj_game_round_$STAMP.sql"

EXISTS=$(mysql -N -B "$DB" -e "SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='$DB' AND TABLE_NAME='mj_game_round' AND COLUMN_NAME='finalHandsJson'")

if [ "$EXISTS" = "0" ]; then
  echo "== 加列 finalHandsJson"
  mysql "$DB" -e "ALTER TABLE mj_game_round
    ADD COLUMN finalHandsJson JSON NULL COMMENT '终局四家手牌与副露 含胡张 用于结算回放核对'
    AFTER payerJson"
else
  echo "== finalHandsJson 已存在，跳过 ALTER"
fi

echo "== 登记 schema 版本"
mysql "$DB" -e "INSERT IGNORE INTO mj_schema_version (versionCode, description, appliedYMDHMS)
  VALUES ('20261029_02', 'mj_game_round.finalHandsJson 终局四家手牌留痕', '$STAMP')"

echo "== 结果"
mysql -t "$DB" -e "SHOW COLUMNS FROM mj_game_round LIKE 'finalHandsJson'"
mysql -t "$DB" -e "SELECT versionCode, description, appliedYMDHMS FROM mj_schema_version ORDER BY recID DESC LIMIT 3"
