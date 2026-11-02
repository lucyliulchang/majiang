"""v1.1.4 界面冒烟：收桌入口（U-6）+ 吃牌可解释提示（B-2）。

做法：本地起一个「静态 + 假 REST + 假 WS」的孪生后端，用真实构建产物（dist / dist-mobile）
连上去，只验证前端渲染与交互，不碰数据库、不需要真实账号。

场景按房间号区分（假 WS 按 code 选快照）：

- `428915` 管理员（ADMIN，未入座）在牌桌上：应看到「结束牌局」，点击后确认 → 发出 `game.finish`；
- `428916` 下家手里 `1万1万2万3万` 遇 `1万`：动作条应同时有「碰」与「吃」，且**不显示**原因提示；
- `428917` 同一手牌摆到非下家：只有「碰」+「只有下家能吃」。

用法（仓库根目录）：

    python plan/tools/smoke_v114.py

产出：`plan/v1.1.4-evidence/*.png` + `smoke-v114.log`（含假 WS 收到的客户端消息）。
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
EVIDENCE = ROOT / "plan" / "v1.1.4-evidence"

HTTP_PORT = 8899
WS_PORT = 8900

ROOM_END_ADMIN = "428915"
ROOM_CHOW_OK = "428916"
ROOM_CHOW_HINT = "428917"

LOG_LINES: list[str] = []
CLIENT_MESSAGES: dict[str, list[dict]] = {}


def log(text: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {text}"
    LOG_LINES.append(line)
    # Windows 控制台默认 GBK，界面文案里有 ♪ 之类的符号会炸；降级输出，证据仍在日志文件里
    print(line.encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)


# ---------------------------------------------------------------- 假快照
def seat_view(seat: int, name: str, host: bool = False, melds: list | None = None) -> dict:
    return {
        "seat": seat,
        "login_id": f"1380000010{seat}",
        "display_name": name,
        "color": "#C9A063",
        "ready": True,
        "connected": True,
        "is_host": host,
        "hand_count": 13,
        "wind": seat,
        "is_dealer": seat == 0,
        "spectator_count": 0,
        "melds": melds or [],
        "round_score": 0,
        "total_score": 0,
    }


ROOM = {
    "room_code": "",
    "room_name": "周末家庭局",
    "host_login_id": "13800000109",
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
        "rounds_per_game": 1,
        "circles_per_game": 1,
    },
}


def build_snapshot(code: str) -> dict:
    """按场景拼快照：只填界面真正会读的字段（其余给安全默认值）。"""
    room = dict(ROOM, room_code=code)
    base = {
        "room": room,
        "self_seat": 0,
        "spectate": None,
        "join_requests": [],
        "seats": [
            seat_view(0, "爸爸", host=False),
            seat_view(1, "妈妈"),
            seat_view(2, "小姨"),
            seat_view(3, "爷爷", host=True),
        ],
        "status": "playing",
        "paused": {"paused": False, "by_seat": None, "note": None},
        "round_no": 1,
        "dealer_seat": 3,
        "round_wind": 0,
        "circle_no": 1,
        "total_circles": 1,
        "rounds_per_circle": 4,
        "round_in_circle": 1,
        "dealer_continue": False,
        "game_total_rounds": 4,
        "hand": [0, 0, 1, 2, 4, 8, 9, 11, 15, 18, 20, 24, 27],
        "drawn": None,
        "turn": 3,
        "phase": "claim",
        "wall_count": 83,
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
        "tenpai": {},
        "deadline": None,
        "claim_deadline": time.time() + 120,
        "result": None,
        "seat_viewer_counts": [0, 0, 0, 0],
    }

    if code == ROOM_END_ADMIN:
        # 管理员观战收桌：legal 为空（不是他的回合），但能力位允许收桌
        base.update(
            {
                "self_seat": None,
                "spectate": {
                    "target_seat": 0,
                    "target_login_id": "13800000100",
                    "viewer_count": 0,
                    "limit_per_seat": 10,
                },
                "phase": "discard",
                "turn": 0,
                "legal": {"actions": [], "claim_tile": None, "claim_from": None},
                "drawn": None,
                "viewer": {"is_host": False, "member_role": "ADMIN", "can_end_game": True},
            }
        )
        return base

    if code == ROOM_CHOW_OK:
        base["viewer"] = {"is_host": False, "member_role": "MEMBER", "can_end_game": False}
        return base

    # 非下家：只有碰，且带原因
    base["legal"] = {
        "actions": [
            {"action": "pong", "tiles": [0, 0], "label": "碰"},
            {"action": "pass", "label": "过"},
        ],
        "claim_tile": 0,
        "claim_from": 3,
        "reason": "discard",
        "chow_hint": "只有下家能吃",
    }
    base["viewer"] = {"is_host": False, "member_role": "MEMBER", "can_end_game": False}
    return base


# ---------------------------------------------------------------- 假 WS
def ws_handler(conn) -> None:
    path = conn.request.path
    code = (parse_qs(urlparse(path).query).get("code") or [""])[0]
    CLIENT_MESSAGES.setdefault(code, [])
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
            CLIENT_MESSAGES[code].append(message)
            log(f"WS← {code} {message.get('type')}")
            kind = message.get("type")
            if kind == "state.resync":
                conn.send(
                    json.dumps({"type": "state.snapshot", "data": build_snapshot(code)}, ensure_ascii=False)
                )
            elif kind == "game.finish":
                conn.send(
                    json.dumps(
                        {
                            "type": "event.game_finished",
                            "data": {
                                "scores": [{"seat": i, "name": f"玩家{i}", "total": 0} for i in range(4)],
                                "aborted": True,
                                "ended_by_seat": None,
                                "ended_by_name": "爸爸",
                                "final": True,
                            },
                        },
                        ensure_ascii=False,
                    )
                )
                conn.send(
                    json.dumps(
                        {"type": "event.room_closed", "data": {"room_code": code, "by": "爸爸"}},
                        ensure_ascii=False,
                    )
                )
            elif kind == "ping":
                conn.send(json.dumps({"type": "pong", "data": {}}))
    except Exception as exc:  # noqa: BLE001 - 冒烟脚本，断连不致命
        log(f"WS 断开 code={code}: {exc!r}")


# ---------------------------------------------------------------- 假 REST + 静态
SESSION = {
    "user": {"login_id": "13800000100", "nick_name": "爸爸", "role": "user"},
    "families": [
        {"family_code": "lianjia", "family_name": "廉家", "member_role": "ADMIN"},
    ],
    "current_family_code": "lianjia",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:  # 静音
        return

    def _json(self, payload: dict, status: int = 200) -> None:
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
        suffix = path.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".mp3": "audio/mpeg",
            ".woff2": "font/woff2",
        }.get(suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if "/api/" in path:
            if path.endswith("/health"):
                return self._json({"ok": True, "version": "1.1.4"})
            if path.endswith("/auth/me"):
                return self._json(SESSION)
            if path.endswith("/user/pref"):
                return self._json(
                    {
                        "last_family_code": "lianjia",
                        "skin_code": None,
                        "sound_enabled": False,
                        "sound_volume": 0,
                        "chat_sound": False,
                        "show_tenpai": True,
                    }
                )
            return self._json({})
        # 桌面产物入口是 index.html，手机产物入口是 mobile.html（vite 多页构建，部署时同款）
        for prefix, root, entry in (
            ("/majiangapp/", DIST, "index.html"),
            ("/mjmobile/", DIST_MOBILE, "mobile.html"),
        ):
            if path.startswith(prefix):
                rel = path[len(prefix) :] or entry
                target = root / rel
                if not target.is_file():
                    target = root / entry  # SPA 回退（history 路由）
                return self._file(target)
        self.send_error(404)


def start_servers() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    server = ws_serve(ws_handler, "127.0.0.1", WS_PORT)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"假后端就绪 http://127.0.0.1:{HTTP_PORT} / ws://127.0.0.1:{WS_PORT}")


INIT_JS = """
(() => {
  localStorage.setItem('mj_token', 'smoke-token-v114');
  localStorage.setItem('mj_user', JSON.stringify({login_id: '13800000100', nick_name: '爸爸', role: 'user'}));
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


def run() -> int:
    from playwright.sync_api import sync_playwright

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    start_servers()
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        log(f"{'PASS' if ok else 'FAIL'} {name}{(' · ' + detail) if detail else ''}")
        if not ok:
            failures.append(f"{name} {detail}".strip())

    with sync_playwright() as p:
        browser = p.chromium.launch()

        def open_page(base: str, code: str, viewport: dict):
            ctx = browser.new_context(viewport=viewport, device_scale_factor=1)
            page = ctx.new_page()
            page.add_init_script(INIT_JS)
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(f"http://127.0.0.1:{HTTP_PORT}{base}room/{code}", wait_until="load")
            page.wait_for_timeout(1800)
            return ctx, page, errors

        # ---- 场景 1：桌面·管理员观战可收桌
        ctx, page, errors = open_page("/majiangapp/", ROOM_END_ADMIN, {"width": 1280, "height": 800})
        end_btn = page.locator("button", has_text="结束牌局")
        check("桌面·管理员看到「结束牌局」", end_btn.count() > 0, f"found={end_btn.count()}")
        page.screenshot(path=str(EVIDENCE / "01-desktop-admin-endgame-entry.png"))
        if end_btn.count() > 0:
            end_btn.first.click()
            page.wait_for_timeout(400)
            confirm = page.locator("button", has_text="结束牌局")
            check("桌面·二次确认弹层出现", confirm.count() >= 2, f"buttons={confirm.count()}")
            page.screenshot(path=str(EVIDENCE / "02-desktop-admin-endgame-confirm.png"))
            confirm.last.click()
            page.wait_for_timeout(900)
            sent = [m.get("type") for m in CLIENT_MESSAGES.get(ROOM_END_ADMIN, [])]
            check("桌面·点击后发出 game.finish", "game.finish" in sent, f"sent={sent}")
            page.screenshot(path=str(EVIDENCE / "03-desktop-admin-endgame-done.png"))
        check("桌面·无 JS 异常", not errors, "; ".join(errors[:3]))
        ctx.close()

        # ---- 场景 2：桌面·碰与吃并存
        ctx, page, errors = open_page("/majiangapp/", ROOM_CHOW_OK, {"width": 1280, "height": 800})
        body = page.inner_text("body")
        check(
            "桌面·动作条同时有「碰」与「吃」",
            "碰" in body and "吃" in body,
            body.replace("\n", " ")[:120].encode("ascii", "replace").decode("ascii"),
        )
        check("桌面·可吃时不显示原因", "只有下家能吃" not in body)
        check("桌面·非房主/管理员无收桌入口", page.locator("button", has_text="结束牌局").count() == 0)
        page.screenshot(path=str(EVIDENCE / "04-desktop-chow-available.png"))
        check("桌面·吃场景无 JS 异常", not errors, "; ".join(errors[:3]))
        ctx.close()

        # ---- 场景 3：桌面·不可吃的原因
        ctx, page, errors = open_page("/majiangapp/", ROOM_CHOW_HINT, {"width": 1280, "height": 800})
        body = page.inner_text("body")
        check("桌面·显示「只有下家能吃」", "只有下家能吃" in body)
        page.screenshot(path=str(EVIDENCE / "05-desktop-chow-hint.png"))
        ctx.close()

        # ---- 场景 4：手机·不可吃的原因（375×667 与 667×375 横屏）
        ctx, page, errors = open_page("/mjmobile/", ROOM_CHOW_HINT, {"width": 667, "height": 375})
        body = page.inner_text("body")
        check("手机·显示「只有下家能吃」", "只有下家能吃" in body)
        page.screenshot(path=str(EVIDENCE / "06-mobile-chow-hint.png"))
        ctx.close()

        # ---- 场景 5：手机·碰与吃并存
        ctx, page, errors = open_page("/mjmobile/", ROOM_CHOW_OK, {"width": 667, "height": 375})
        body = page.inner_text("body")
        check("手机·动作条同时有「碰」与「吃」", "碰" in body and "吃" in body)
        page.screenshot(path=str(EVIDENCE / "07-mobile-chow-available.png"))
        ctx.close()

        # ---- 场景 6：手机·管理员收桌入口（在「更多」面板）
        ctx, page, errors = open_page("/mjmobile/", ROOM_END_ADMIN, {"width": 667, "height": 375})
        more = page.locator('button[aria-label^="更多"]')
        check("手机·存在「更多」入口", more.count() > 0, f"found={more.count()}")
        if more.count() > 0:
            more.first.click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(EVIDENCE / "08-mobile-admin-more-sheet.png"))
            body = page.inner_text("body")
            check("手机·更多里出现「结束牌局」", "结束牌局" in body)
        ctx.close()

        browser.close()

    (EVIDENCE / "smoke-v114.log").write_text("\n".join(LOG_LINES), encoding="utf-8")
    (EVIDENCE / "smoke-v114-ws-messages.json").write_text(
        json.dumps(CLIENT_MESSAGES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
