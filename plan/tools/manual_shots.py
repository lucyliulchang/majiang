"""生成《家庭麻将使用手册》（docs/manual.html）要用的截图。

做法与 `smoke_v114.py` 一致：本地起一个「静态 + 假 REST + 假 WS」的孪生后端，
接真实构建产物（`code/frontend/dist` / `dist-mobile`），只喂界面需要的快照，
不碰数据库、不需要真实账号，因此截图可随时重跑、内容可控。

覆盖场景（文件名即 docs/manual.html 里的引用名）：

- 01-register   注册页（已填示例）
- 02-login      登录页
- 03-lobby      大厅（家里的牌桌 + 邀请码入座）
- 04-create-room 开一桌（规则族 / 模板 / 圈数）
- 05-room-waiting 进桌等人（准备 / 开始牌局）
- 06-round-start  开局后的牌桌
- 07-claim-hu     可胡时的动作条
- 08-claim-chow   可吃时的动作条
- 09-chow-pick    吃：选两张手牌
- 10-claim-kong   可杠时的动作条
- 11-round-result 本局结算（赢）
- 12-mobile-lobby  手机·大厅
- 13-mobile-table  手机·牌桌（可吃）
- 14-mobile-result 手机·结算

用法（仓库根目录）：

    python plan/tools/manual_shots.py

产出：`docs/img/manual/*.png`；日志写到 `plan/manual-evidence/shots.log`。
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from websockets.sync.server import serve as ws_serve

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "code" / "frontend" / "dist"
DIST_MOBILE = ROOT / "code" / "frontend" / "dist-mobile"
OUT = ROOT / "docs" / "img" / "manual"
LOGDIR = ROOT / "plan" / "manual-evidence"

HTTP_PORT = 8893
WS_PORT = 8894

# 按房间号区分场景（假 WS 据此返回不同快照）
ROOM_WAIT = "510001"
ROOM_PLAY = "510002"
ROOM_HU = "510003"
ROOM_CHOW = "510004"
ROOM_KONG = "510005"
ROOM_RESULT = "510006"

LOG_LINES: list[str] = []


def log(text: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {text}"
    LOG_LINES.append(line)
    print(line.encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)


# ---------------------------------------------------------------- 假快照
ROOM_META = {
    "room_code": "",
    "room_id": 9021,
    "room_name": "周末家庭局",
    "host_login_id": "13800010001",
    "family_code": "lianjia",
    "family_name": "廉家",
    "rule_name": "柏氏家庭局",
    "rule_family_code": "baishi",
    "rule_brief": {
        "base_score": 1,
        "fan_mode": "exponential",
        "fan_cap": 8,
        "allow_chow": True,
        "turn_timeout": {"enabled": False, "seconds": 15},
        "kong_score": {"enabled": True, "exposed": 1, "hidden": 2, "added": 1},
        "ting_hint": True,
        "patterns": ["标准胡", "七对"],
        "rounds_per_game": 4,
        "circles_per_game": 4,
    },
}

SEAT_NAMES = ["爸爸", "妈妈", "小姨", "爷爷"]
SEAT_COLORS = ["#C9A063", "#D98C8C", "#8CB0D9", "#8CD9A6"]


def seat_view(seat: int, ready: bool = True, host: bool = False) -> dict:
    return {
        "seat": seat,
        "login_id": f"1380001000{seat + 1}",
        "display_name": SEAT_NAMES[seat],
        "color": SEAT_COLORS[seat],
        "ready": ready,
        "connected": True,
        "is_host": host,
        "hand_count": 13,
        "wind": seat,
        "is_dealer": seat == 0,
        "spectator_count": 0,
        "melds": [],
        "round_score": 0,
        "total_score": 12 - seat * 4,
    }


FAN_ITEMS = [
    {"id": "menqing", "name": "门清", "fan": 1, "count": 1},
    {"id": "duanyao", "name": "断幺", "fan": 1, "count": 1},
    {"id": "yibangao", "name": "一般高", "fan": 1, "count": 1},
    {"id": "quemen", "name": "缺门", "fan": 1, "count": 1},
]
WIN_HAND = [0, 1, 2, 3, 4, 5, 10, 11, 11, 11, 12, 27, 27, 28]


def build_snapshot(code: str) -> dict:
    room = dict(ROOM_META, room_code=code)
    base = {
        "room": room,
        "self_seat": 0,
        "spectate": None,
        "join_requests": [],
        "seats": [seat_view(i, host=(i == 0)) for i in range(4)],
        "status": "playing",
        "paused": {"paused": False, "by_seat": None, "note": None},
        "round_no": 2,
        "dealer_seat": 0,
        "round_wind": 0,
        "circle_no": 1,
        "total_circles": 4,
        "rounds_per_circle": 4,
        "round_in_circle": 2,
        "dealer_continue": False,
        "game_total_rounds": 16,
        "hand": [0, 1, 2, 4, 5, 9, 10, 12, 15, 18, 19, 27, 29],
        "drawn": 31,
        "turn": 0,
        "phase": "discard",
        "wall_count": 84,
        "discards": [[], [], [], []],
        "last_discard": None,
        "legal": {"actions": [{"action": "discard"}], "claim_tile": None, "claim_from": None},
        "tenpai": {},
        "deadline": None,
        "claim_deadline": None,
        "result": None,
        "seat_viewer_counts": [0, 0, 0, 0],
        "viewer": {"is_host": True, "member_role": "OWNER", "can_end_game": True},
    }

    if code == ROOM_WAIT:
        # 4 人到齐、全部准备：房主可点「开始牌局」
        base.update(
            {
                "status": "waiting",
                "phase": "waiting",
                "turn": None,
                "hand": [],
                "drawn": None,
                "wall_count": 0,
                "discards": [[], [], [], []],
                "legal": {"actions": [], "claim_tile": None, "claim_from": None},
            }
        )
        return base

    if code == ROOM_HU:
        # 小姨（seat 2）打出 3 筒，我可以胡
        base.update(
            {
                "phase": "claim",
                "turn": 2,
                "drawn": None,
                "hand": [0, 1, 2, 4, 5, 9, 10, 12, 15, 18, 19, 27, 29],
                "discards": [[], [], [11], []],
                "last_discard": {"seat": 2, "tile": 11},
                "legal": {
                    "actions": [
                        {"action": "hu", "tiles": [], "label": "胡"},
                        {"action": "pass", "label": "过"},
                    ],
                    "claim_tile": 11,
                    "claim_from": 2,
                    "reason": "discard",
                },
                "claim_deadline": time.time() + 120,
            }
        )
        return base

    if code == ROOM_CHOW:
        # 爷爷（seat 3，上家）打出 1 万：碰与吃并存
        base.update(
            {
                "phase": "claim",
                "turn": 3,
                "drawn": None,
                "hand": [0, 0, 1, 2, 4, 5, 9, 11, 15, 18, 20, 24, 27],
                "discards": [[], [], [], [0]],
                "last_discard": {"seat": 3, "tile": 0},
                "legal": {
                    "actions": [
                        {"action": "pong", "tiles": [0, 0], "label": "碰"},
                        {"action": "chow", "tiles": [1, 2], "label": "吃（二万三万）"},
                        {"action": "pass", "label": "过"},
                    ],
                    "claim_tile": 0,
                    "claim_from": 3,
                    "reason": "discard",
                },
                "claim_deadline": time.time() + 120,
            }
        )
        return base

    if code == ROOM_KONG:
        # 爷爷打出 4 万，我手里三张 4 万：可明杠
        base.update(
            {
                "phase": "claim",
                "turn": 3,
                "drawn": None,
                "hand": [3, 3, 3, 5, 6, 8, 9, 11, 15, 18, 20, 24, 27],
                "discards": [[], [], [], [3]],
                "last_discard": {"seat": 3, "tile": 3},
                "legal": {
                    "actions": [
                        {"action": "kong", "tiles": [3, 3, 3], "label": "杠（四万）"},
                        {"action": "pong", "tiles": [3, 3], "label": "碰"},
                        {"action": "pass", "label": "过"},
                    ],
                    "claim_tile": 3,
                    "claim_from": 3,
                    "reason": "discard",
                },
                "claim_deadline": time.time() + 120,
            }
        )
        return base

    if code == ROOM_RESULT:
        base.update(
            {
                "phase": "settled",
                "turn": None,
                "drawn": None,
                "hand": [0, 1, 2, 4, 5, 9, 10, 12, 15, 18, 19, 27, 29],
                "round_no": 3,
                "wall_count": 62,
                "discards": [[0, 1], [11], [10, 24], [3, 15]],
                "last_discard": {"seat": 3, "tile": 15},
                "legal": {"actions": [], "claim_tile": None, "claim_from": None},
                "seats": [
                    dict(seat_view(0, host=True), total_score=-8),
                    dict(seat_view(1), total_score=24),
                    dict(seat_view(2), total_score=-8),
                    dict(seat_view(3), total_score=-8),
                ],
                "result": {
                    "round_no": 3,
                    "winner_seat": 1,
                    "win_type": "self_draw",
                    "winning_tile": 11,
                    "pattern_id": "standard",
                    "fan_total": 4,
                    "fan_items": FAN_ITEMS,
                    "score_delta": [-8, 24, -8, -8],
                    "breakdown": {
                        "pattern_name": "柏氏标准胡",
                        "lines": FAN_ITEMS,
                        "fan_raw": 4,
                        "fan_total": 4,
                        "capped": False,
                    },
                    "is_last_round": False,
                    "winners": [
                        {
                            "seat": 1,
                            "win_type": "self_draw",
                            "winning_tile": 11,
                            "pattern_id": "standard",
                            "fan_items": FAN_ITEMS,
                            "fan_total": 4,
                            "multipliers": {"self_draw": 2, "dealer": 1},
                        }
                    ],
                    "kong_delta": [0, 0, 0, 0],
                    "multipliers": {"self_draw": 2, "dealer": 1},
                    "final_hands": [
                        {
                            "seat": 1,
                            "login_id": "13800010002",
                            "display_name": "妈妈",
                            "concealed": WIN_HAND,
                            "melds": [],
                            "is_winner": True,
                            "win_type": "self_draw",
                            "winning_tile": 11,
                            "winning_tile_index": 9,
                        }
                    ],
                },
            }
        )
        return base

    # ROOM_PLAY：默认出牌阶段（牌河有内容，看起来像真实对局）
    base.update(
        {
            "discards": [[0, 5, 9, 16], [11, 12, 18], [19, 24, 33], [3, 8, 15]],
            "last_discard": {"seat": 3, "tile": 15},
        }
    )
    return base


# ---------------------------------------------------------------- 假 WS
def ws_handler(conn) -> None:
    path = conn.request.path
    code = (parse_qs(urlparse(path).query).get("code") or [""])[0]
    log(f"WS 连接 code={code}")
    snapshot = build_snapshot(code)
    conn.send(
        json.dumps(
            {
                "type": "room.welcome",
                "data": {"room": snapshot["room"], "self_seat": snapshot["self_seat"], "chat": []},
            },
            ensure_ascii=False,
        )
    )
    conn.send(json.dumps({"type": "state.snapshot", "data": snapshot}, ensure_ascii=False))
    try:
        for raw in conn:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if message.get("type") == "state.resync":
                conn.send(
                    json.dumps({"type": "state.snapshot", "data": build_snapshot(code)}, ensure_ascii=False)
                )
            elif message.get("type") == "ping":
                conn.send(json.dumps({"type": "pong", "data": {}}))
    except Exception as exc:  # noqa: BLE001 - 截图脚本，断连不致命
        log(f"WS 断开 code={code}: {exc!r}")


# ---------------------------------------------------------------- 假 REST + 静态
SESSION = {
    "user": {
        "login_id": "13800010001",
        "nick_name": "爸爸",
        "avatar_id": "",
        "role_name": "customer",
        "role": "member",
        "active_flag": "Y",
    },
    "families": [
        {
            "family_code": "lianjia",
            "family_name": "廉家",
            "owner_login_id": "13800010001",
            "default_rule_family_code": "baishi",
            "default_skin_code": None,
            "member_role": "OWNER",
            "status": "ACTIVE",
            "sort_order": 1,
        }
    ],
    "current_family_code": "lianjia",
}

ROOMS = [
    {
        "id": 9021,
        "room_code": ROOM_WAIT,
        "family_code": "lianjia",
        "room_name": "周末家庭局",
        "host_login_id": "13800010001",
        "host_name": "爸爸",
        "template_id": 7,
        "rule_name": "柏氏家庭局",
        "rule_family_code": "baishi",
        "status": "OPEN",
        "player_count": 4,
        "spectator_count": 0,
        "created_at": "2026-11-06 19:20:00",
    },
    {
        "id": 9022,
        "room_code": ROOM_RESULT,
        "family_code": "lianjia",
        "room_name": "饭后一盘",
        "host_login_id": "13800010003",
        "host_name": "小姨",
        "template_id": 7,
        "rule_name": "柏氏家庭局",
        "rule_family_code": "baishi",
        "status": "OPEN",
        "player_count": 3,
        "spectator_count": 2,
        "created_at": "2026-11-06 20:05:00",
    },
]

RULE_CONFIG = {
    "base_score": 1,
    "fan_mode": "exponential",
    "fan_cap": 8,
    "allow_chow": True,
    "turn_timeout": {"enabled": False, "seconds": 15},
    "kong_score": {"enabled": True, "exposed": 1, "hidden": 2, "added": 1},
    "ting_hint": {"enabled": True},
    "rounds_per_game": 4,
    "circles_per_game": 4,
    "fan_table": [{"id": f"fan{i}", "name": f"番种{i}", "fan": 1} for i in range(35)],
}

RULE_TEMPLATES = [
    {
        "id": 7,
        "template_code": "baishi_default",
        "family_code": None,
        "rule_family_code": "baishi",
        "template_name": "柏氏家庭局",
        "description": "底分 1、封顶 8 番、可吃、杠计分，最常用的家庭配置",
        "config": RULE_CONFIG,
        "is_preset": True,
        "is_active": True,
        "owner_login_id": None,
        "created_at": "2026-10-01 00:00:00",
        "updated_at": "2026-10-01 00:00:00",
    },
    {
        "id": 8,
        "template_code": "baishi_nofan",
        "family_code": None,
        "rule_family_code": "baishi",
        "template_name": "柏氏·不封顶",
        "description": "番数不封顶，适合老手",
        "config": dict(RULE_CONFIG, fan_cap=None, fan_mode="linear"),
        "is_preset": True,
        "is_active": True,
        "owner_login_id": None,
        "created_at": "2026-10-01 00:00:00",
        "updated_at": "2026-10-01 00:00:00",
    },
]

RULE_FAMILIES = [
    {
        "rule_family_code": "baishi",
        "rule_family_name": "柏氏",
        "engine_code": "baishi",
        "tile_set_code": "standard",
        "capability": {},
        "status": "ACTIVE",
        "sort_order": 1,
        "ready": True,
    }
]

STATS = {"total_score": 86, "games_played": 12, "best_game": 48, "worst_game": -32, "rounds_won": 21}

PREF = {
    "last_family_code": "lianjia",
    "skin_code": None,
    "sound_enabled": False,
    "sound_volume": 0,
    "chat_sound": False,
    "show_tenpai": True,
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:  # 静音
        return

    def _json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".woff2": "font/woff2",
        }.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if "/api/" in path or "/majiangapi/" in path:
            if path.endswith("/health"):
                return self._json({"ok": True, "version": "1.1.5"})
            if path.endswith("/auth/options"):
                return self._json(
                    {
                        "register_enabled": True,
                        "password_reset_enabled": True,
                        "verify_code_cooldown_seconds": 60,
                    }
                )
            if path.endswith("/auth/me"):
                return self._json(SESSION)
            if path.endswith("/user/pref"):
                return self._json(PREF)
            if path.endswith("/history/stats"):
                return self._json(STATS)
            if path.endswith("/rule-families"):
                return self._json(RULE_FAMILIES)
            if path.endswith("/rules"):
                return self._json(RULE_TEMPLATES)
            if path.endswith("/rooms"):
                return self._json(ROOMS)
            if path.endswith("/skins"):
                return self._json([])
            return self._json({})
        for prefix, root, entry in (
            ("/majiangapp/", DIST, "index.html"),
            ("/mjmobile/", DIST_MOBILE, "mobile.html"),
        ):
            if path.startswith(prefix):
                rel = path[len(prefix) :] or entry
                target = root / rel
                if not target.is_file():
                    target = root / entry  # SPA 回退
                return self._file(target)
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        return self._json({"ok": True})

    def do_PUT(self) -> None:  # noqa: N802
        return self.do_POST()

    def do_PATCH(self) -> None:  # noqa: N802
        return self.do_POST()


def start_servers() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    server = ws_serve(ws_handler, "127.0.0.1", WS_PORT)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"假后端就绪 http://127.0.0.1:{HTTP_PORT} / ws://127.0.0.1:{WS_PORT}")


INIT_JS = """
(() => {
  localStorage.setItem('mj_token', 'manual-shots-token');
  localStorage.setItem('mj_user', JSON.stringify({login_id: '13800010001', nick_name: '爸爸', role: 'member'}));
  const RealWS = window.WebSocket;
  const target = '%s';
  window.WebSocket = function (url, protocols) {
    let next = String(url);
    if (next.indexOf('/majiangws') >= 0 || next.indexOf('/ws') >= 0) {
      next = next.replace(/wss?:\\/\\/[^/]+/, 'ws://' + target);
    }
    return protocols === undefined ? new RealWS(next) : new RealWS(next, protocols);
  };
  window.WebSocket.prototype = RealWS.prototype;
  Object.assign(window.WebSocket, {CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3});
})();
""" % f"127.0.0.1:{WS_PORT}"

# 登录页/注册页不需要登录态：清掉 token，避免守卫把人弹回大厅
GUEST_JS = """
(() => {
  localStorage.removeItem('mj_token');
  localStorage.removeItem('mj_user');
})();
"""


def run() -> int:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    LOGDIR.mkdir(parents=True, exist_ok=True)
    start_servers()
    base = f"http://127.0.0.1:{HTTP_PORT}"
    failures: list[str] = []

    def shot(page, name: str) -> None:
        path = OUT / f"{name}.png"
        page.screenshot(path=str(path))
        log(f"截图 {path.name}")

    def check(name: str, ok: bool, detail: str = "") -> None:
        log(f"{'PASS' if ok else 'FAIL'} {name}{(' · ' + detail) if detail else ''}")
        if not ok:
            failures.append(f"{name} {detail}".strip())

    with sync_playwright() as p:
        browser = p.chromium.launch()

        def open_desktop(route: str, init_js: str = INIT_JS, wait: int = 1600):
            ctx = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1, locale="zh-CN")
            page = ctx.new_page()
            page.add_init_script(init_js)
            page.goto(f"{base}/majiangapp/{route}", wait_until="load")
            page.wait_for_timeout(wait)
            return ctx, page

        def open_mobile(route: str, init_js: str = INIT_JS, wait: int = 1600, viewport: dict | None = None):
            ctx = browser.new_context(
                viewport=viewport or {"width": 844, "height": 390},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                locale="zh-CN",
            )
            page = ctx.new_page()
            page.add_init_script(init_js)
            page.goto(f"{base}/mjmobile/{route}", wait_until="load")
            page.wait_for_timeout(wait)
            return ctx, page

        # ---- 01 注册页
        ctx, page = open_desktop("register", GUEST_JS, 1200)
        page.fill('input[placeholder="11 位手机号"]', "13800010005")
        page.fill('input[placeholder="6 位数字"]', "836512")
        page.fill('input[placeholder="6-32 位，不含空格"]', "family2026")
        page.fill('input[placeholder="再输入一次"]', "family2026")
        page.fill('input[placeholder="比如 爸爸"]', "奶奶")
        page.wait_for_timeout(400)
        check("注册页渲染", "注册账号" in page.inner_text("body"))
        shot(page, "01-register")
        ctx.close()

        # ---- 02 登录页
        ctx, page = open_desktop("login", GUEST_JS, 1200)
        page.fill('input[placeholder="比如 13800000000"]', "13800010001")
        page.fill('input[placeholder="输入你的密码"]', "family2026")
        page.wait_for_timeout(300)
        check("登录页渲染", "登录牌桌" in page.inner_text("body"))
        shot(page, "02-login")
        ctx.close()

        # ---- 03 大厅
        ctx, page = open_desktop("", INIT_JS, 1800)
        body = page.inner_text("body")
        check("大厅列出家里的牌桌", ROOM_WAIT in body and "饭后一盘" in body)
        shot(page, "03-lobby")

        # ---- 04 开一桌（弹窗）
        page.locator("button", has_text="创建牌桌").first.click()
        page.wait_for_timeout(1200)
        body = page.inner_text("body")
        check("开桌弹窗有规则族与圈数", "开一桌" in body and "柏氏" in body and "打几圈" in body)
        shot(page, "04-create-room")
        ctx.close()

        # ---- 05 进桌等人
        ctx, page = open_desktop(f"room/{ROOM_WAIT}", INIT_JS, 1800)
        body = page.inner_text("body")
        check("等待开局界面", "等人齐了就开始" in body and "开始牌局" in body)
        shot(page, "05-room-waiting")
        ctx.close()

        # ---- 06 开局后的牌桌
        ctx, page = open_desktop(f"room/{ROOM_PLAY}", INIT_JS, 1800)
        body = page.inner_text("body")
        check("开局牌桌有牌墙与手牌", "牌墙" in body)
        shot(page, "06-round-start")
        ctx.close()

        # ---- 07 可胡
        ctx, page = open_desktop(f"room/{ROOM_HU}", INIT_JS, 1800)
        body = page.inner_text("body")
        check("可胡时动作条有「胡」", "胡" in body)
        shot(page, "07-claim-hu")
        ctx.close()

        # ---- 08 可吃 / 09 选两张
        ctx, page = open_desktop(f"room/{ROOM_CHOW}", INIT_JS, 1800)
        body = page.inner_text("body")
        check("可吃时动作条有「吃」", "吃" in body and "碰" in body)
        shot(page, "08-claim-chow")
        chow_btn = page.locator("button", has_text="吃").first
        if chow_btn.count() > 0:
            chow_btn.click()
            page.wait_for_timeout(500)
            # 点第一个候选组合，演示「已选两张 → 确认吃」
            cand = page.locator('button[aria-label^="套用"]')
            if cand.count() > 0:
                cand.first.click()
                page.wait_for_timeout(400)
            check("吃牌选牌态出现", "确认吃" in page.inner_text("body"))
            shot(page, "09-chow-pick")
        ctx.close()

        # ---- 10 可杠
        ctx, page = open_desktop(f"room/{ROOM_KONG}", INIT_JS, 1800)
        body = page.inner_text("body")
        check("可杠时动作条有「杠」", "杠" in body)
        shot(page, "10-claim-kong")
        ctx.close()

        # ---- 11 结算
        ctx, page = open_desktop(f"room/{ROOM_RESULT}", INIT_JS, 2200)
        body = page.inner_text("body")
        check("结算面板显示胡牌与番种", "结算" in body and "门清" in body)
        shot(page, "11-round-result")
        ctx.close()

        # ---- 12~14 手机端（大厅/结算竖屏，牌桌横屏）
        ctx, page = open_mobile("", INIT_JS, 1800, {"width": 390, "height": 844})
        check("手机大厅渲染", "邀请码" in page.inner_text("body") or "牌桌" in page.inner_text("body"))
        shot(page, "12-mobile-lobby")
        ctx.close()

        ctx, page = open_mobile(f"room/{ROOM_CHOW}", INIT_JS, 2000)
        shot(page, "13-mobile-table")
        ctx.close()

        # 手机版牌桌只支持横屏（竖屏会弹「请把手机横过来」遮罩），结算同样按横屏取
        ctx, page = open_mobile(f"room/{ROOM_RESULT}", INIT_JS, 2200)
        shot(page, "14-mobile-result")
        ctx.close()

        browser.close()

    LOGDIR.joinpath("shots.log").write_text("\n".join(LOG_LINES), encoding="utf-8")
    log(f"完成：{len(failures)} 项失败")
    for item in failures:
        log(f"  - {item}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    raise SystemExit(run())
