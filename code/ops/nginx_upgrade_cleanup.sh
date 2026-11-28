#!/bin/bash
# cleanup smoke-test artifacts (production nginx untouched)
rm -rf /tmp/ngx-smoke /tmp/ngx-smoke-bin
rm -f /home/codeops/probe_upload_module.sh
echo "=== production nginx status"
systemctl is-active nginx 2>/dev/null || pgrep -a nginx | head -3
/usr/local/nginx/nginx -v 2>&1
echo "=== site check"
curl -s -o /dev/null -w 'majiangapp: %{http_code}\n' -k https://127.0.0.1/majiangapp/ -H 'Host: www.iottest.online'
echo "=== artifacts left in /home/lianyi/software"
ls -l /home/lianyi/software/nginx-1.30.8/objs/nginx /home/lianyi/software/*.tar.gz | grep -E '1\.30\.8|3\.5\.9|upload-module-2'
ls -ld /home/lianyi/software/nginx-1.30.8 /home/lianyi/software/openssl-3.5.9 /home/lianyi/software/nginx-upload-module-2.4.0
