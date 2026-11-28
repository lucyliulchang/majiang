#!/bin/bash
# Replace /usr/local/nginx/nginx with the newly built 1.30.8 (backup + hot reload + verify + auto rollback)
set -uo pipefail
NEW=/home/lianyi/software/nginx-1.30.8/objs/nginx
CUR=/usr/local/nginx/nginx
CONF=/usr/local/nginx/nginx.conf
TS=$(date +%Y%m%d_%H%M%S)
BK=/data/backup/nginx_$TS
ERRLOG=/usr/local/nginx/logs/error.log

echo "################ PRE-CHECK"
echo "current: $($CUR -v 2>&1)"
echo "new    : $($NEW -v 2>&1)"
echo -n "upstream 8005: "; (ss -lnt | grep -q ':8005 ' && echo up) || echo down
echo -n "errlog: "; ls -l "$ERRLOG" 2>&1
echo -n "conf.d size: "; du -sh /usr/local/nginx/conf.d 2>/dev/null
echo
echo "################ 1. BACKUP"
mkdir -p "$BK" || exit 1
cp -a "$CUR" "$BK/nginx-1.26.1"
cp -a "$CONF" "$BK/nginx.conf"
cp -a /usr/local/nginx/conf.d "$BK/conf.d"
systemctl show nginx -p MainPID -p ExecMainStartTimestamp >"$BK/state.txt" 2>&1
sha256sum "$BK/nginx-1.26.1" "$BK/nginx.conf" >>"$BK/SHA256SUMS"
echo "backup dir: $BK"; ls -l "$BK"

echo
echo "################ 2. CONFIG TEST WITH NEW BINARY"
"$NEW" -t -c "$CONF" 2>&1 || { echo "CONFIG TEST FAILED -> abort, nothing changed"; exit 1; }

echo
echo "################ 3. INSTALL NEW BINARY"
install -m 0755 -o root -g root "$NEW" "$CUR" || { echo "install failed"; exit 1; }
ls -l "$CUR"; "$CUR" -v 2>&1; sha256sum "$CUR" "$NEW"

echo
echo "################ 4. HOT RELOAD (zero downtime)"
OLDPID=$(cat /usr/local/nginx/nginx.pid 2>/dev/null)
OLDWORKERS=$(pgrep -P "$OLDPID" | tr '\n' ' ')
echo "master=$OLDPID old workers: $OLDWORKERS"
systemctl reload nginx; echo "reload rc=$?"
sleep 4

echo
echo "################ 5. VERIFY"
curl -s -o /dev/null -m 10 -w 'http 127.0.0.1/        -> %{http_code}\n' http://127.0.0.1/
echo -n "Server header: "; curl -sI -m 10 http://127.0.0.1/ | grep -i '^Server:'
echo -n "TLS 443: "; curl -s -o /dev/null -m 10 -k -w '%{http_code} %{ssl_verify_result}\n' https://127.0.0.1/majiangapp/ -H 'Host: www.iottest.online'
echo -n "majiangapp http: "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1/majiangapp/ -H 'Host: www.iottest.online'
echo -n "mjmobile  http: "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1/mjmobile/ -H 'Host: www.iottest.online'
echo -n "acis on 8160:   "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1:8160/acis

NEWPID=$(cat /usr/local/nginx/nginx.pid 2>/dev/null)
echo "master pid now: $NEWPID"
for p in $(pgrep -P "$NEWPID"); do
  echo "  worker $p -> $(readlink /proc/$p/exe) $(stat -c '%y' /proc/$p/exe 2>/dev/null | cut -d. -f1)"
done
echo -n "old worker still alive? "; for p in $OLDWORKERS; do [ -d /proc/$p ] && echo -n "$p "; done; echo

echo
echo "################ 6. UPLOAD SMOKE TEST ON PRODUCTION (8160 /upload)"
echo "test-nuevo-1308" >/tmp/ngx_up_test.txt
BEFORE=$(ls -1t /data/webserver/temp/*/ 2>/dev/null | head -1)
CODE=$(curl -s -m 30 -o /tmp/ngx_up_resp.txt -w '%{http_code}' \
  -F "submit=1" -F "description=nginx-1.30.8 upgrade test" -F "index=0" \
  -F "file=@/tmp/ngx_up_test.txt" http://127.0.0.1:8160/upload)
echo "upload http_code=$CODE  (200 ok / 502 = upstream 8005 down but file still stored)"
echo "--- response head:"; head -c 300 /tmp/ngx_up_resp.txt; echo
echo "--- newest files in /data/webserver/temp:"
find /data/webserver/temp -type f -newermt '-2 minutes' -printf '%T@ %p %s\n' 2>/dev/null | sort -n | tail -3

echo
echo "################ 7. LOGS"
tail -15 "$ERRLOG" 2>&1
echo "--- journal (nginx last 10)"
journalctl -u nginx -n 10 --no-pager 2>&1 | tail -12

echo
echo "################ RESULT"
if curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1/ | grep -qE '200|301|302|403|404'; then
  echo "SERVICE OK"
else
  echo "SERVICE FAILED -> ROLLBACK"
  install -m 0755 -o root -g root "$BK/nginx-1.26.1" "$CUR"
  systemctl reload nginx
  sleep 3
  echo "rolled back to: $($CUR -v 2>&1)"
  exit 2
fi
echo "backup dir for rollback: $BK"
echo "rollback cmd: install -m 0755 -o root -g root $BK/nginx-1.26.1 /usr/local/nginx/nginx && systemctl reload nginx"
