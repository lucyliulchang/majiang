#!/usr/bin/env bash
# 只更新前端产物： sudo bash remote-deploy-front.sh   （包已在 /tmp/mj_dist.tar.gz）
set -euo pipefail
rm -rf /tmp/mj_dist
mkdir -p /tmp/mj_dist
tar xzf /tmp/mj_dist.tar.gz -C /tmp/mj_dist
rsync -a --delete --exclude 'tiles/' /tmp/mj_dist/ /data/webserver/majiangapp/
chown -R majiang:majiang /data/webserver/majiangapp
chmod -R a+rX /data/webserver/majiangapp
echo "前端已更新：$(ls /data/webserver/majiangapp | tr '\n' ' ')"
curl -sS -o /dev/null -w 'index=%{http_code}\n' http://127.0.0.1/majiangapp/
