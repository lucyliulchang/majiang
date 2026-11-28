#!/bin/bash
# probe nginx-upload-module maintained fork tags/urls
set -u
echo "=== API tags (sysadmin-labs)"
curl -s --max-time 25 https://api.github.com/repos/sysadmin-labs/nginx-upload-module/tags \
  | grep -o '"name": *"[^"]*"' | head -20
echo "=== API releases"
curl -s --max-time 25 https://api.github.com/repos/sysadmin-labs/nginx-upload-module/releases \
  | grep -o '"tag_name": *"[^"]*"' | head -10
echo "=== repo meta"
curl -s --max-time 25 https://api.github.com/repos/sysadmin-labs/nginx-upload-module \
  | grep -oE '"(full_name|default_branch|pushed_at|updated_at|fork)": *("[^"]*"|true|false)'
echo "=== candidate tarball urls"
for u in \
  https://codeload.github.com/sysadmin-labs/nginx-upload-module/tar.gz/2.4.0 \
  https://codeload.github.com/sysadmin-labs/nginx-upload-module/tar.gz/v2.4.0 \
  https://codeload.github.com/sysadmin-labs/nginx-upload-module/tar.gz/refs/heads/master \
  https://codeload.github.com/sysadmin-labs/nginx-upload-module/tar.gz/refs/heads/main ; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$u")
  echo "$code  $u"
done
