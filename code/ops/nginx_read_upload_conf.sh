#!/bin/bash
echo "=== nginx.conf 40..110"
sed -n '40,110p' /usr/local/nginx/nginx.conf
echo
echo "=== nginx.conf 255,310"
sed -n '255,310p' /usr/local/nginx/nginx.conf
echo
echo "=== upload temp store dir"
ls -ld /data/webserver/temp 2>&1; ls /data/webserver/temp 2>&1 | head
echo
echo "=== hfile locations"
grep -n "hfile" -A6 /usr/local/nginx/nginx.conf | head -40
