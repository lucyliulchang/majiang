#!/bin/bash
# 定期统计包装（生产/测试服通用）：调 stats_report.py，把 CSV 落在 /data/backup/stats。
#
# 用法：
#   sudo bash stats_daily.sh                # 全量
#   sudo bash stats_daily.sh --days 1       # 最近 1 天（每天跑一次就是「当日战报」）
#   sudo bash stats_daily.sh --days 30 --with-fan-items
#
# 注意：本脚本**不安装任何定时任务**，只在被调用时跑一次；需要定期执行时再由人工手动
# 加 cron（默认不加，部署阶段也未配置）。
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${OUT_DIR:-/data/backup/stats}"
ENV_FILE="${ENV_FILE:-/data/majiang/src/.env}"
PYTHON_BIN="${PYTHON_BIN:-/data/majiang/venv/bin/python}"

mkdir -p "$OUT_DIR" || exit 1
exec "$PYTHON_BIN" "$SCRIPT_DIR/stats_report.py" --env-file "$ENV_FILE" --out-dir "$OUT_DIR" "$@"
