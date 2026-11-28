#!/bin/bash
# Stage 1: download nginx 1.30.8 + OpenSSL 3.5.9 + nginx-upload-module v2.4.0 into /home/lianyi/software
set -uo pipefail
cd /home/lianyi/software || exit 1

NGINX_VER=1.30.8
OSSL_VER=3.5.9
UP_VER=v2.4.0

echo "=== 0. build deps"
for p in libpcre2-dev zlib1g-dev build-essential perl; do
  dpkg -l "$p" >/dev/null 2>&1 && echo "ok   $p" || echo "MISS $p"
done
echo "pcre2-config: $(command -v pcre2-config || echo none)"
ls /usr/include/pcre2.h /usr/include/zlib.h 2>&1

echo "=== 1. nginx source"
if [ ! -f "nginx-${NGINX_VER}.tar.gz" ]; then
  curl -fL --retry 3 --max-time 300 -o "nginx-${NGINX_VER}.tar.gz" "https://nginx.org/download/nginx-${NGINX_VER}.tar.gz" || exit 1
fi
if [ ! -f "nginx-${NGINX_VER}.tar.gz.sha256" ]; then
  curl -fsL --max-time 60 -o "nginx-${NGINX_VER}.tar.gz.sha256" "https://nginx.org/download/nginx-${NGINX_VER}.tar.gz.sha256" || echo "no sha256 file published"
fi
ls -l "nginx-${NGINX_VER}.tar.gz"
sha256sum "nginx-${NGINX_VER}.tar.gz"

echo "=== 2. openssl source"
if [ ! -f "openssl-${OSSL_VER}.tar.gz" ]; then
  curl -fL --retry 3 --max-time 300 -o "openssl-${OSSL_VER}.tar.gz" "https://www.openssl.org/source/openssl-${OSSL_VER}.tar.gz" || exit 1
fi
if [ ! -f "openssl-${OSSL_VER}.tar.gz.sha256" ]; then
  curl -fsL --max-time 60 -o "openssl-${OSSL_VER}.tar.gz.sha256" "https://www.openssl.org/source/openssl-${OSSL_VER}.tar.gz.sha256" || echo "no sha256 file"
fi
ls -l "openssl-${OSSL_VER}.tar.gz"
sha256sum "openssl-${OSSL_VER}.tar.gz"
if [ -f "openssl-${OSSL_VER}.tar.gz.sha256" ]; then
  cat "openssl-${OSSL_VER}.tar.gz.sha256"
fi

echo "=== 3. nginx-upload-module ${UP_VER}"
if [ ! -f "nginx-upload-module-2.4.0.tar.gz" ]; then
  curl -fL --retry 3 --max-time 300 -o "nginx-upload-module-2.4.0.tar.gz" \
    "https://codeload.github.com/sysadmin-labs/nginx-upload-module/tar.gz/${UP_VER}" || exit 1
fi
ls -l nginx-upload-module-2.4.0.tar.gz
sha256sum nginx-upload-module-2.4.0.tar.gz

echo "=== 4. extract"
[ -d "nginx-${NGINX_VER}" ] || tar xzf "nginx-${NGINX_VER}.tar.gz" || exit 1
[ -d "openssl-${OSSL_VER}" ] || tar xzf "openssl-${OSSL_VER}.tar.gz" || exit 1
if [ ! -d "nginx-upload-module-2.4.0" ]; then
  rm -rf nginx-upload-module-2.4.0
  mkdir -p nginx-upload-module-2.4.0
  tar xzf nginx-upload-module-2.4.0.tar.gz -C nginx-upload-module-2.4.0 --strip-components=1 || exit 1
fi
chown -R lianyi:lianyi "nginx-${NGINX_VER}" "openssl-${OSSL_VER}" nginx-upload-module-2.4.0 *.tar.gz 2>/dev/null

echo "=== 5. sanity: module sources"
ls nginx-upload-module-2.4.0 | head -20
echo "--- config file:"
sed -n '1,40p' nginx-upload-module-2.4.0/config
echo "--- version/changelog hints:"
grep -rInE '2\.4\.0|1\.0\.0' nginx-upload-module-2.4.0/Changelog* 2>/dev/null | head -10
echo "=== DONE stage1"
