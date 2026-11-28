#!/bin/bash
# Stage 2: configure nginx 1.30.8 with OpenSSL 3.5.9 + upload-module v2.4.0 (NO install)
set -uo pipefail
SRC=/home/lianyi/software
cd "$SRC/nginx-1.30.8" || exit 1

echo "=== upload module CHANGELOG (head)"
sed -n '1,40p' "$SRC/nginx-upload-module-2.4.0/CHANGELOG.md"
echo
echo "=== pcre2 related code in module"
grep -n "pcre2\|pcre_exec\|NGX_REGEX" "$SRC/nginx-upload-module-2.4.0/src/ngx_http_upload_module.c" | head -20
echo
echo "=== make clean"
make clean >/dev/null 2>&1
LOG="$SRC/configure-1.30.8.log"
./configure \
  --sbin-path=/usr/local/nginx/nginx \
  --conf-path=/usr/local/nginx/nginx.conf \
  --pid-path=/usr/local/nginx/nginx.pid \
  --with-http_ssl_module \
  --with-openssl="$SRC/openssl-3.5.9" \
  --add-module="$SRC/nginx-upload-module-2.4.0" >"$LOG" 2>&1
rc=$?
echo "=== configure exit=$rc"
tail -40 "$LOG"
exit $rc
