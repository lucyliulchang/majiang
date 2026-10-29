#!/usr/bin/env bash
# 家庭麻将 · 手机版发版脚本（在目标服务器本机执行）
#
# 用法： sudo bash deploy-mobile.sh <发布包目录>
#   发布包结构：
#     <pkg>/dist-mobile/   ← code/frontend 里 `npm run build:mobile` 的产物全部内容
#
# 与 deploy.sh 的区别：只同步 /data/webserver/mjmobile，不碰后端、不重启 mahjong 服务，
# 因此发手机版不会打断 PC 版或正在进行的牌局。
set -euo pipefail

PKG=${1:?用法: deploy-mobile.sh <发布包目录>}
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/data/backup
WEB_DIR=/data/webserver/mjmobile

log() { printf '\n== %s\n' "$*"; }

[ -d "$PKG/dist-mobile" ] || { echo "缺少 $PKG/dist-mobile"; exit 1; }
# 入口文件叫 mobile.html：产物里没有它就说明构建跑错了（跑成了 PC 的 dist）
[ -f "$PKG/dist-mobile/mobile.html" ] || {
  echo "缺少 dist-mobile/mobile.html —— 请先在 code/frontend 执行 npm run build:mobile"
  exit 1
}

# ---------- 1) 备份当前手机版 ----------
mkdir -p "$BACKUP_DIR" "$WEB_DIR"
if [ -n "$(ls -A "$WEB_DIR" 2>/dev/null || true)" ]; then
  log "备份当前手机版 → $BACKUP_DIR/mjmobile_$STAMP.tgz"
  tar czf "$BACKUP_DIR/mjmobile_$STAMP.tgz" -C /data/webserver mjmobile
else
  log "首次发布：$WEB_DIR 为空，跳过备份"
fi

# ---------- 2) 同步产物 ----------
log "同步手机版 → $WEB_DIR"
# assets 只增不删：浏览器可能还持有上一版 mobile.html（引用旧哈希 JS），
# 如果把旧 assets 一并删掉，老页面会 404 掉脚本 —— 表现为「只剩背景、没有文字」。
rsync -a --delete --exclude 'assets/' "$PKG/dist-mobile/" "$WEB_DIR/"
rsync -a "$PKG/dist-mobile/assets/" "$WEB_DIR/assets/"
find "$WEB_DIR/assets" -type f -mtime +14 -delete 2>/dev/null || true
chown -R majiang:majiang "$WEB_DIR"
chmod -R a+rX "$WEB_DIR"

# ---------- 3) 校验（只查静态入口，不依赖后端）----------
log "校验入口与资源"
curl -fsS -o /dev/null -w 'mobile.html  HTTP %{http_code}\n' http://127.0.0.1/mjmobile/mobile.html
curl -fsS -o /dev/null -w 'tileart/1m   HTTP %{http_code}\n' http://127.0.0.1/mjmobile/tileart/1m.svg
curl -fsS -o /dev/null -w 'history 回退 HTTP %{http_code}\n' http://127.0.0.1/mjmobile/history

echo
echo "OK  回滚点： $STAMP"
echo "    回滚： sudo rm -rf $WEB_DIR && sudo tar xzf $BACKUP_DIR/mjmobile_$STAMP.tgz -C /data/webserver"
echo "    手机版地址： https://www.iottest.online/mjmobile/"
