#!/usr/bin/env bash
# 把 /tmp/mj_pkg/nginx-majiang.conf 装成 conf.d 片段，并在 80/443 两个 server 内 include。
# 幂等：已 include 过就只覆盖片段内容，不重复插入。
set -euo pipefail

CONF=/usr/local/nginx/nginx.conf
INC_DIR=/usr/local/nginx/conf.d
SNIPPET_SRC=/tmp/mj_pkg/nginx-majiang.conf
# 主机是编译安装：可执行文件在 /usr/local/nginx/nginx（没有 sbin/）
NGINX_BIN=/usr/local/nginx/nginx
NGINX_ARGS="-c /usr/local/nginx/nginx.conf"
STAMP=$(date +%Y%m%d_%H%M%S)

[ -f "$SNIPPET_SRC" ] || { echo "缺少 $SNIPPET_SRC"; exit 1; }

echo "== 备份 $CONF -> $CONF.bak_$STAMP"
cp -a "$CONF" "$CONF.bak_$STAMP"

mkdir -p "$INC_DIR"
install -m 644 "$SNIPPET_SRC" "$INC_DIR/majiang.conf"

if grep -q 'conf.d/majiang.conf' "$CONF"; then
  echo "== include 已存在，跳过插入"
else
  echo "== 在 80 / 443 的 server 段插入 include"
  python3 - "$CONF" <<'PY'
import sys

path = sys.argv[1]
with open(path, encoding='utf-8') as handle:
    lines = handle.read().split('\n')

out = []
inserted = 0
for index, line in enumerate(lines):
    out.append(line)
    stripped = line.strip()
    if not stripped.startswith('server_name'):
        continue
    head = '\n'.join(lines[max(0, index - 6):index])
    if 'listen       80' in head or 'listen       443' in head:
        out.append('        include /usr/local/nginx/conf.d/majiang.conf;')
        inserted += 1

with open(path, 'w', encoding='utf-8') as handle:
    handle.write('\n'.join(out))
print(f'inserted={inserted}')
PY
fi

echo "== nginx -t"
"$NGINX_BIN" $NGINX_ARGS -t
echo "== reload"
"$NGINX_BIN" $NGINX_ARGS -s reload
sleep 1
echo "== 自检"
curl -sS -o /dev/null -w 'index=%{http_code} ' http://127.0.0.1/majiangapp/
curl -sS -o /dev/null -w 'spa=%{http_code} ' http://127.0.0.1/majiangapp/rules
curl -sS -o /dev/null -w 'api=%{http_code} ' http://127.0.0.1/majiangapi/health
curl -sS -o /dev/null -w 'api-legacy=%{http_code}\n' http://127.0.0.1/api/health
