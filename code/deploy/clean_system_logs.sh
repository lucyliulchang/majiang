#!/usr/bin/env bash
#Filename: clean_system_logs.sh
#Description: 系统级兜底清理(需 root, 由 root crontab 每日 00:10 拉起)
#             1) /data/backup 发版与 DB 备份: 删除超过 KEEP_DAYS 的, 但始终保留最近 KEEP_MIN 个
#             2) /var/log/btmp: 超过 BTMP_MAX_MB 则清空, 并删除 btmp.1 等轮转档
#                (btmp 记录 ssh 爆破失败登录, 无追溯价值, 不清理会按月涨到数百 MB)
#             3) auth.log / fail2ban.log 由 logrotate(weekly + maxsize 50M) 管理, 本脚本只记录体积
#Usage:
#   sudo /data/majiang/ops/clean_system_logs.sh            # 正常清理
#   sudo /data/majiang/ops/clean_system_logs.sh --dry-run  # 只打印将删除的内容
set -uo pipefail

BACKUP_DIR=${MJ_BACKUP_DIR:-/data/backup}
KEEP_DAYS=${MJ_BACKUP_KEEP_DAYS:-30}
KEEP_MIN=${MJ_BACKUP_KEEP_MIN:-10}
BTMP_MAX_MB=${BTMP_MAX_MB:-100}
LOG_DIR=${MJ_LOG_DIR:-/data/majiang/log/schedule}
LOG_FILE=${LOG_DIR}/system_clean.log

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%F %T')] $*"; }

# 单文件队列: 按修改时间从旧到新逐行输出
listOldestFirst() {
    /usr/bin/find "$1" -maxdepth 1 -type f "${@:2}" -printf '%T@ %p\n' 2>/dev/null \
        | /usr/bin/sort -n | /usr/bin/awk '{$1=""; sub(/^ /,""); print}'
}

cleanBackupDir() {
    [ -d "$BACKUP_DIR" ] || { log "backup dir missing: $BACKUP_DIR"; return 0; }

    mapfile -t allFiles < <(listOldestFirst "$BACKUP_DIR" \( -name '*.tgz' -o -name '*.tar.gz' -o -name '*.sql' -o -name '*.sql.gz' \))
    total=${#allFiles[@]}
    log "backup dir=$BACKUP_DIR files=$total keepDays=$KEEP_DAYS keepMin=$KEEP_MIN"
    [ "$total" -eq 0 ] && return 0

    cutoff=$(( $(date +%s) - KEEP_DAYS * 86400 ))
    deletable=$(( total - KEEP_MIN ))
    [ "$deletable" -lt 0 ] && deletable=0

    removed=0
    for filePath in "${allFiles[@]}"; do
        [ "$removed" -ge "$deletable" ] && break
        mtime=$(/usr/bin/stat -c %Y "$filePath" 2>/dev/null || echo 0)
        [ "$mtime" -ge "$cutoff" ] && break
        if [ "$DRY_RUN" -eq 1 ]; then
            log "[dry-run] would delete $filePath"
        else
            /bin/rm -f "$filePath" && log "deleted $filePath"
        fi
        removed=$((removed + 1))
    done
    log "backup removed=$removed"
}

cleanBtmp() {
    limit=$(( BTMP_MAX_MB * 1024 * 1024 ))

    for filePath in /var/log/btmp.1 /var/log/btmp.2; do
        [ -f "$filePath" ] || continue
        if [ "$DRY_RUN" -eq 1 ]; then
            log "[dry-run] would delete $filePath ($(/usr/bin/du -h "$filePath" | /usr/bin/cut -f1))"
        else
            /bin/rm -f "$filePath" && log "deleted $filePath"
        fi
    done

    [ -f /var/log/btmp ] || return 0
    size=$(/usr/bin/stat -c %s /var/log/btmp 2>/dev/null || echo 0)
    if [ "$size" -gt "$limit" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            log "[dry-run] would truncate /var/log/btmp (${size} bytes > ${limit})"
        else
            /usr/bin/truncate -s 0 /var/log/btmp && log "truncated /var/log/btmp (was ${size} bytes)"
        fi
    else
        log "btmp size=${size} bytes (limit ${limit}), skip"
    fi
}

reportSyslogs() {
    for filePath in /var/log/auth.log /var/log/fail2ban.log /var/log/syslog; do
        [ -f "$filePath" ] || continue
        log "size $(/usr/bin/du -h "$filePath" | /usr/bin/cut -f1) $filePath"
    done
    log "journald: $(journalctl --disk-usage 2>/dev/null | /usr/bin/tail -1)"
}

{
    log "===== clean start (dryRun=$DRY_RUN) ====="
    cleanBackupDir
    cleanBtmp
    reportSyslogs
    log "===== clean done, disk: $(/bin/df -h / | /usr/bin/awk 'NR==2{print $3"/"$2" ("$5")"}') ====="
} >> "$LOG_FILE" 2>&1
