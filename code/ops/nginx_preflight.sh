#!/bin/bash
# preflight (read-only) before replacing /usr/local/nginx/nginx
echo "=== systemd unit"
systemctl cat nginx 2>&1 | head -30
echo
echo "=== active state / start time"
systemctl is-active nginx; systemctl is-enabled nginx 2>&1
systemctl show nginx -p ExecMainStartTimestamp -p MainPID 2>&1
echo
echo "=== processes"
ps -o pid,ppid,user,etime,cmd -C nginx 2>&1
echo
echo "=== binary"
ls -l /usr/local/nginx/nginx; /usr/local/nginx/nginx -V 2>&1 | tail -2
echo
echo "=== upload module usage in config"
grep -rn "upload_" /usr/local/nginx/nginx.conf /usr/local/nginx/conf.d/ 2>/dev/null | head -20
echo "(count: $(grep -rc "upload_" /usr/local/nginx/nginx.conf /usr/local/nginx/conf.d/ 2>/dev/null | tr '\n' ' '))"
echo
echo "=== ssl / v2 usage"
grep -rn "listen" /usr/local/nginx/nginx.conf /usr/local/nginx/conf.d/ 2>/dev/null | head -20
echo
echo "=== included configs"
grep -n "include" /usr/local/nginx/nginx.conf | head -20
echo
echo "=== backup dir space"
df -h /data 2>/dev/null | tail -1
ls -ld /data/backup 2>&1
echo
echo "=== listening sockets"
ss -lntp | grep -E ':80|:443'
