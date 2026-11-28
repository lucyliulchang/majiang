#!/bin/bash
echo "=== linked openssl string in running binary"
strings /usr/local/nginx/nginx | grep -m3 -E '^OpenSSL 3\.[0-9]+\.[0-9]+'
/usr/local/nginx/nginx -V 2>&1 | grep -E 'nginx version|built with'
echo
echo "=== upload module compiled symbols"
strings /usr/local/nginx/nginx | grep -m5 -E 'upload_pass_form_field|upload_store|upload_cleanup'
echo
echo "=== leftover test artifacts in upload store (last 30 min)"
find /data/webserver/temp -type f -newermt '-30 minutes' -printf '%T@ %p %s\n' 2>/dev/null | sort -n | tail -5
echo "(none above = upload_cleanup handled the 502 test)"
echo
echo "=== 5xx in error log since restart"
grep -a '2026/11/24 18:5' /usr/local/nginx/logs/error.log | grep -ac emergency || true
tail -3 /usr/local/nginx/logs/error.log
echo
echo "=== remove temp scripts"
rm -f /home/codeops/ngx_*.sh /home/codeops/nginx_*.sh /tmp/ngx_up_test.txt /tmp/ngx_up_resp.txt
ls /home/codeops/*.sh 2>&1
echo
echo "=== backup dir"
ls -l /data/backup/nginx_20261124_184947
