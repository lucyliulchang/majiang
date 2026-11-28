#!/bin/bash
# Stage 4: verify built binary (build-only, no deployment)
SRC=/home/lianyi/software
BIN="$SRC/nginx-1.30.8/objs/nginx"
LOG="$SRC/make-1.30.8.log"

echo "=== binary"
ls -l "$BIN"
"$BIN" -V 2>&1
echo
echo "=== upload module in module list"
grep -n upload "$SRC/nginx-1.30.8/objs/ngx_modules.c"
echo "=== http_v2 present? (expected: no, same as current build)"
grep -c ngx_http_v2_module "$SRC/nginx-1.30.8/objs/ngx_modules.c"
echo
echo "=== compile warnings mentioning upload/openssl"
grep -inE 'warning' "$LOG" | grep -iE 'upload|ssl' | head -20
echo "warnings total: $(grep -ic warning "$LOG")"
echo
echo "=== live nginx still untouched"
ls -l /usr/local/nginx/nginx
/usr/local/nginx/nginx -v 2>&1
echo
echo "=== config test with new binary (read-only; running nginx unaffected)"
"$BIN" -t 2>&1
echo
echo "=== restore ownership to lianyi"
chown -R lianyi:lianyi "$SRC/nginx-1.30.8" "$SRC/openssl-3.5.9" "$SRC/nginx-upload-module-2.4.0"
chown lianyi:lianyi "$SRC"/*.log "$SRC"/*.tar.gz
ls -ld "$SRC/nginx-1.30.8" "$SRC/openssl-3.5.9" "$SRC/nginx-upload-module-2.4.0" "$SRC"/*.tar.gz
