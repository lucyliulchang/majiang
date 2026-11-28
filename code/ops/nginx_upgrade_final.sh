#!/bin/bash
rm -f /tmp/ngx-smoke-bin
rm -f /home/codeops/nginx_upgrade_*.sh
echo "=== final artifacts"
ls -l /home/lianyi/software/nginx-1.30.8/objs/nginx
ls -l /home/lianyi/software/nginx-1.30.8.tar.gz /home/lianyi/software/openssl-3.5.9.tar.gz /home/lianyi/software/nginx-upload-module-2.4.0.tar.gz
ls -ld /home/lianyi/software/nginx-1.30.8 /home/lianyi/software/openssl-3.5.9 /home/lianyi/software/nginx-upload-module-2.4.0
echo "=== tmp check"
ls -l /tmp/ngx-smoke-bin 2>&1 | tail -1
echo "=== production"
pgrep -a nginx | head -2
