#!/bin/bash
# Restart nginx so the new 1.30.8 master actually runs, then verify everything
set -uo pipefail
BK=/data/backup/nginx_20261124_184947
CUR=/usr/local/nginx/nginx
ERRLOG=/usr/local/nginx/logs/error.log

echo "################ before restart"
echo "on-disk binary: $($CUR -v 2>&1)"
OLDMASTER=$(cat /usr/local/nginx/nginx.pid 2>/dev/null); echo "old master=$OLDMASTER"
pgrep -P "$OLDMASTER" | while read p; do echo "  worker $p -> $(readlink /proc/$p/exe)"; done

echo
echo "################ restart"
systemctl restart nginx; rc=$?; echo "restart rc=$rc"
sleep 3
echo -n "is-active: "; systemctl is-active nginx
echo -n "is-enabled: "; systemctl is-enabled nginx 2>&1

echo
echo "################ process check"
NEWMASTER=$(cat /usr/local/nginx/nginx.pid 2>/dev/null); echo "new master=$NEWMASTER"
ps -o pid,ppid,user,etime,cmd -p "$NEWMASTER" 2>&1
for p in $(pgrep -P "$NEWMASTER"); do echo "  worker $p -> $(readlink /proc/$p/exe)"; done

echo
echo "################ traffic check"
echo -n "Server header: "; curl -sI -m 10 http://127.0.0.1/ | grep -i '^Server:'
echo -n "http  /                 : "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1/
echo -n "http  /majiangapp/      : "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1/majiangapp/ -H 'Host: www.iottest.online'
echo -n "http  /mjmobile/        : "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1/mjmobile/ -H 'Host: www.iottest.online'
echo -n "https /majiangapp/      : "; curl -s -o /dev/null -m 10 -k -w '%{http_code}\n' https://127.0.0.1/majiangapp/ -H 'Host: www.iottest.online'
echo -n "8160  /acis             : "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1:8160/acis
echo -n "8000  backend direct    : "; curl -s -o /dev/null -m 10 -w '%{http_code}\n' http://127.0.0.1:8000/docs
echo "--- TLS handshake"
echo | timeout 8 openssl s_client -connect 127.0.0.1:443 -servername www.iottest.online 2>/dev/null | grep -E 'Protocol|Cipher|subject=' | head -5

echo
echo "################ listening sockets"
ss -lntp 2>/dev/null | grep -E ':80 |:443 |:8160 '

echo
echo "################ error log (since restart)"
tail -8 "$ERRLOG"
echo "--- any emerg/alert/crit/alerts?"
grep -aE '\[(emerg|alert|crit)\]' "$ERRLOG" | tail -5
echo "--- journal"
journalctl -u nginx -n 8 --no-pager 2>&1 | tail -9

echo
echo "################ upload module: production-regex filter test in sandbox"
T=/tmp/ngx-rx; rm -rf "$T"; mkdir -p "$T"/{logs,store}
cat >"$T/recv.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n=int(self.headers.get('Content-Length',0)); open('/tmp/ngx-rx/recv.txt','wb').write(self.rfile.read(n))
        self.send_response(200); self.send_header('Content-Length','2'); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self,*a): pass
HTTPServer(('127.0.0.1',18092),H).serve_forever()
PY
python3 "$T/recv.py" & echo $! >"$T/r.pid"
cat >"$T/nginx.conf" <<CONF
daemon on;
worker_processes 1;
error_log $T/logs/error.log;
pid $T/logs/nginx.pid;
events { worker_connections 32; }
http {
  access_log off;
  client_body_temp_path $T/body;
  server {
    listen 127.0.0.1:18091;
    location /upload {
      upload_pass /hfile;
      upload_store $T/store;
      upload_store_access all:rw;
      upload_set_form_field \$upload_field_name.name "\$upload_file_name";
      upload_set_form_field \$upload_field_name.path "\$upload_tmp_path";
      upload_aggregate_form_field "\$upload_field_name.md5" "\$upload_file_md5";
      upload_pass_form_field "^submit\$|^description\$|^index\$";
      upload_cleanup 400 404 499 500-505;
    }
    location /hfile { proxy_pass http://127.0.0.1:18092; }
  }
}
CONF
mkdir -p "$T/body"
echo "regex-test-1308" >"$T/f.txt"
"$CUR" -p "$T" -c "$T/nginx.conf" -t >/dev/null 2>&1 && "$CUR" -p "$T" -c "$T/nginx.conf" && sleep 1
echo -n "upload(hit upstream 18092) http_code="
curl -s -o /dev/null -m 15 -w '%{http_code}\n' -F "submit=1" -F "description=prod-regex" -F "index=0" -F "keepme=drop" -F "file=@$T/f.txt" http://127.0.0.1:18091/upload
sleep 1
echo "--- forwarded body (expect submit/description/index + file.* only, no keepme):"
cat "$T/recv.txt" 2>/dev/null | grep -a 'name=' | sed 's/^/    /'
"$CUR" -p "$T" -c "$T/nginx.conf" -s quit 2>/dev/null; sleep 1; kill "$(cat "$T/r.pid")" 2>/dev/null; rm -rf "$T"

echo
echo "################ RESULT"
curl -s -m 5 -o /dev/null -w 'root=%{http_code} ' http://127.0.0.1/
curl -s -m 5 -o /dev/null -w 'majiangapp=%{http_code}\n' http://127.0.0.1/majiangapp/ -H 'Host: www.iottest.online'
echo "running master: $(readlink /proc/$NEWMASTER/exe)"
echo "rollback: install -m 0755 -o root -g root $BK/nginx-1.26.1 /usr/local/nginx/nginx && systemctl restart nginx"
