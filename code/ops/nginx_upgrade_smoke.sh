#!/bin/bash
# Sandbox smoke test for the newly built nginx (unprivileged, port 18081, /tmp only)
SRCBIN=/home/lianyi/software/nginx-1.30.8/objs/nginx
T=/tmp/ngx-smoke
rm -rf "$T" /tmp/ngx-smoke-bin
mkdir -p "$T"/{conf,logs,body,proxy,fastcgi,uwsgi,scgi,store}
sudo -n install -m 0755 "$SRCBIN" /tmp/ngx-smoke-bin || { echo "copy binary failed"; exit 1; }
BIN=/tmp/ngx-smoke-bin

cat >"$T/receiver.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(n)
        open('/tmp/ngx-smoke/recv.txt', 'wb').write(data)
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')
    def log_message(self, *a):
        pass
HTTPServer(('127.0.0.1', 18082), H).serve_forever()
PY
python3 "$T/receiver.py" & echo $! >"$T/recv.pid"

cat >"$T/conf/nginx.conf" <<'CONF'
daemon on;
worker_processes 1;
error_log /tmp/ngx-smoke/logs/error.log info;
pid /tmp/ngx-smoke/logs/nginx.pid;
events { worker_connections 64; }
http {
    access_log off;
    client_body_temp_path /tmp/ngx-smoke/body;
    proxy_temp_path       /tmp/ngx-smoke/proxy;
    fastcgi_temp_path     /tmp/ngx-smoke/fastcgi;
    uwsgi_temp_path       /tmp/ngx-smoke/uwsgi;
    scgi_temp_path        /tmp/ngx-smoke/scgi;
    server {
        listen 127.0.0.1:18081;
        location /upload {
            upload_pass            @upstream;
            upload_store           /tmp/ngx-smoke/store 1;
            upload_store_access    user:rw;
            upload_set_form_field  $upload_field_name.name "$upload_file_name";
            upload_set_form_field  $upload_field_name.path "$upload_tmp_path";
            upload_pass_form_field "^foo$";
            upload_cleanup         400 404 499 500-505;
        }
        location @upstream {
            proxy_pass http://127.0.0.1:18082;
        }
    }
}
CONF

echo "hello-upload-1234" >"$T/file.txt"
"$BIN" -p "$T" -c "$T/conf/nginx.conf" -t 2>&1 || { kill "$(cat "$T/recv.pid")"; exit 1; }
"$BIN" -p "$T" -c "$T/conf/nginx.conf" 2>&1 || { kill "$(cat "$T/recv.pid")"; exit 1; }
sleep 1

echo "=== curl multipart upload (foo=bar kept, baz=qux should be dropped, file stored)"
curl -s -o /dev/null -w 'http_code=%{http_code}\n' -F "foo=bar" -F "baz=qux" -F "file=@$T/file.txt" http://127.0.0.1:18081/upload
sleep 1
echo "--- body forwarded upstream:"
cat "$T/recv.txt" 2>/dev/null
echo
echo "--- stored file:"
ls -l "$T/store"
cat "$T/store"/* 2>/dev/null
echo "--- nginx error log tail:"
tail -5 "$T/logs/error.log"

"$BIN" -p "$T" -c "$T/conf/nginx.conf" -s quit 2>/dev/null
sleep 1
kill "$(cat "$T/recv.pid")" 2>/dev/null
echo "=== smoke test done"
