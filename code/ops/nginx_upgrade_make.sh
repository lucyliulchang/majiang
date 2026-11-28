#!/bin/bash
# Stage 3: make nginx 1.30.8 (build only, NO make install)
SRC=/home/lianyi/software
LOG="$SRC/make-1.30.8.log"
cd "$SRC/nginx-1.30.8" || exit 1
: >"$LOG"
nohup setsid make -j2 >>"$LOG" 2>&1 &
echo "started pid=$!  log=$LOG"
