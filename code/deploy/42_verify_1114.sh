#!/usr/bin/env bash
# v1.1.4 发版后校验：关键文件内容 + 服务器上跑一次「一炮三响」引擎自检 + 前端产物指纹
set -uo pipefail

APP=/data/majiang/src
# 对外域名按环境注入，仓库里只放示例值：export MJ_PUBLIC_BASE_URL=https://<你的域名>
MJ_PUBLIC_BASE_URL="${MJ_PUBLIC_BASE_URL:-https://www.test.com}"

echo "== 1) 关键改动是否已落盘"
grep -n "advance=False" "$APP/game/families/sichuan/engine.py" | head -3
grep -n '"is_out"' "$APP/realtime/snapshot.py" | head -3
grep -n "_hu_recorded_text" "$APP/realtime/room.py" | head -3

echo
echo "== 2) 引擎自检（一炮三响必须三家都进结算）"
cat >/tmp/mj_multihu_check.py <<'PY'
import sys
sys.path.insert(0, "/data/majiang/src")
from game.engine import SeatState
from game.families import registry
from game.tiles import counts_from_tiles

_SUITS = {"m": 0, "p": 1, "s": 2}


def parse_hand(text):
    tiles, pending = [], []
    for ch in text:
        if ch.isdigit():
            pending.append(int(ch))
            continue
        if ch in " ,":
            pending.clear()
            continue
        if ch in _SUITS:
            base = _SUITS[ch]
            tiles.extend(base * 9 + n - 1 for n in pending)
            pending.clear()
        elif ch == "z":
            tiles.extend(27 + n - 1 for n in pending)
            pending.clear()
        else:
            raise ValueError(ch)
    return tiles


seats = [
    SeatState(seat=i, login_id=f"1380000000{i}", display_name=f"玩家{i}", color="#C9A063")
    for i in range(4)
]
engine = registry.create_engine(
    "sichuan", registry.config_model_of("sichuan")(), seats, dealer_seat=0, round_no=1
)
engine.start_round()
mapping = {
    0: "123p456p789p11s59m9m",
    1: "123m456m789m11p78m",
    2: "111m222m333m44m78m",
    3: "555m666m777m99m78m",
}
for seat in range(4):
    engine.seats[seat].counts = counts_from_tiles(parse_hand(mapping[seat]))
    engine.seats[seat].melds = []
    engine.seats[seat].discards = []
engine.turn = 0
engine.phase = "discard"
engine.claim = None
engine.last_draw = None

engine.apply_action(0, {"action": "discard", "tiles": [8]})
for seat in (1, 2, 3):
    engine.apply_action(seat, {"action": "hu"})

winners = [item["seat"] for item in engine.winners]
delta = engine.result.score_delta if engine.result else []
print("winners:", winners)
print("phase:", engine.phase)
print("score_delta:", delta, "sum:", sum(delta))
assert winners == [1, 2, 3], f"一炮三响丢赢家：{winners}"
assert engine.phase == "settled", engine.phase
assert sum(delta) == 0, delta
assert all(delta[seat] > 0 for seat in (1, 2, 3)), delta
print("MULTI_HU_CHECK_OK")
PY

set -a; . "$APP/.env"; set +a
cd "$APP"
sudo -n -u majiang /data/majiang/venv/bin/python /tmp/mj_multihu_check.py
rc=$?
rm -f /tmp/mj_multihu_check.py
echo "自检退出码: $rc"

echo
echo "== 3) 前端产物是否包含 v1.1.4 新界面文案"
for f in /data/webserver/majiangapp/assets/index-*.js /data/webserver/mjmobile/assets/mobile-*.js; do
  [ -f "$f" ] || continue
  printf '%s -> 已胡=%s 多人胡牌=%s\n' "$(basename "$f")" \
    "$(grep -c '已胡' "$f" 2>/dev/null || echo 0)" \
    "$(grep -c '多人胡牌' "$f" 2>/dev/null || echo 0)"
done

echo
echo "== 4) 版本与房态"
curl -sS -m 3 http://127.0.0.1:8000/api/health; echo
curl -sS -m 8 "${MJ_PUBLIC_BASE_URL}/majiangapi/health"; echo
grep -o 'assets/index-[a-zA-Z0-9._-]*' /data/webserver/majiangapp/index.html | head -1
grep -o 'assets/mobile-[a-zA-Z0-9._-]*' /data/webserver/mjmobile/mobile.html | head -1
systemctl is-active mahjong
