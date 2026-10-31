"""v1.1.0 生产冒烟：4 个 WS 机器人打 1 局柏氏，再走「结束牌局」收桌。

只走 04 §9 公开协议（REST 开桌 + WS 入座/开局/出牌/结算/结束），不改任何代码；
证据（逐条断言 + 协议关键帧）写到 JSON。

用法： sudo bash -c 'cd /data/majiang/src && /data/majiang/venv/bin/python \
        /home/codeops/mj_deploy2/smoke_bots.py /home/codeops/mj_deploy2/smoke_evidence.json'
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt
import websockets

ENV_PATH = Path("/data/majiang/src/.env")
ENV: dict[str, str] = {}
for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    ENV[key.strip()] = value.strip().strip('"').strip("'")

SECRET = ENV["SECRET_KEY"]
BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000/ws"
FAMILY_CODE = "fam_29e6"
TEMPLATE_ID = 7  # baishi_default
ROOM_NAME = "v1.1.0 冒烟-勿动"

LOGINS = ["13910710766", "13801324342", "18516181670", "13838718468"]
HOST = LOGINS[0]


def token(login: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": login, "role": "member", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm="HS256",
    )


def http(method: str, path: str, payload: dict | None = None, who: str = HOST):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token(who)}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode() or "null")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def pick_discard(hand: list[int]) -> int | None:
    """贪心出牌：优先打「孤立」的牌（孤张 < 相邻 < 对子 < 刻子），让机器人能真的听牌。"""
    if not hand:
        return None
    counts: dict[int, int] = {}
    for tile in hand:
        counts[tile] = counts.get(tile, 0) + 1
    best: int | None = None
    best_score: float | None = None
    for tile in hand:
        score = counts[tile] * 4.0
        if tile < 27:
            suit = tile // 9
            for step, weight in ((-2, 1.0), (-1, 2.0), (1, 2.0), (2, 1.0)):
                near = tile + step
                if 0 <= near < 27 and near // 9 == suit:
                    score += counts.get(near, 0) * weight
        else:
            # 字牌只认同张
            score += (counts[tile] - 1) * 0.5
        if best_score is None or score < best_score:
            best, best_score = tile, score
    return best


class Bot:
    def __init__(self, login: str, room_code: str, state: "RunState") -> None:
        self.login = login
        self.room_code = room_code
        self.state = state
        self.seat: int | None = None
        self.ready = False
        self.last_key: tuple | None = None
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.closed = asyncio.Event()

    async def send(self, msg_type: str, data: dict | None = None) -> None:
        if self.ws is None:
            return
        await self.ws.send(json.dumps({"type": msg_type, "data": data or {}}))

    async def run(self) -> None:
        url = f"{WS_BASE}?token={token(self.login)}&code={self.room_code}"
        async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
            self.ws = ws
            self.state.log("connect", {"login": self.login})
            try:
                async for raw in ws:
                    message = json.loads(raw)
                    await self.on_message(message.get("type", ""), message.get("data") or {})
                    if self.closed.is_set():
                        break
            except websockets.ConnectionClosed:
                self.state.log("ws_closed", {"login": self.login})

    async def on_message(self, msg_type: str, data: dict) -> None:
        if msg_type == "room.welcome":
            self.seat = data.get("self_seat")
            self.state.log(
                "welcome",
                {
                    "login": self.login,
                    "seat": self.seat,
                    "room": data.get("room", {}).get("room_code"),
                    "rule": data.get("room", {}).get("rule_name"),
                    "rule_brief": data.get("room", {}).get("rule_brief"),
                },
            )
            await self.send("seat.ready")
            return

        if msg_type == "seat.ready" or msg_type == "event.ready_changed":
            seat = data.get("seat")
            self.state.ready[seat] = bool(data.get("ready"))
            return

        if msg_type == "event.settled":
            self.state.settle(data)
            return

        if msg_type == "event.game_finished":
            self.state.game_finished(data)
            return

        if msg_type == "event.room_closed":
            self.state.room_closed(data)
            self.closed.set()
            return

        if msg_type == "error":
            self.state.log("error_frame", {"login": self.login, **data})
            # 出错后允许重试同一局面（例如座位重排导致的一次性误判）
            self.last_key = None
            return

        if msg_type == "state.snapshot":
            if data.get("result") and not self.state.settled_payload:
                self.state.settle(data["result"])
            await self.act(data)

    async def act(self, snapshot: dict) -> None:
        if self.state.settled_payload:
            return
        # 开局抽座会重排物理座位：以快照里的 self_seat 为准（welcome 里的座位号可能已过期）
        if snapshot.get("self_seat") is not None:
            self.seat = snapshot.get("self_seat")
        if self.seat is None:
            return
        phase = snapshot.get("phase")
        turn = snapshot.get("turn")
        legal = snapshot.get("legal") or {}
        actions = [item.get("action") for item in legal.get("actions") or []]

        if phase == "discard" and turn == self.seat:
            # 牌墙每摸一张就少一张 → (局号, 牌墙) 是唯一局面键，避免同一回合被去重挡住
            key = ("discard", snapshot.get("round_no"), snapshot.get("wall_count"), turn)
            if self.last_key == key:
                return
            self.last_key = key
            if "hu" in actions:
                await self.send("game.action", {"action": "hu"})
                self.state.log("action", {"login": self.login, "action": "hu", "phase": phase})
                return
            hand = snapshot.get("hand") or []
            tile = pick_discard(hand)
            if tile is None:
                return
            await self.send("game.action", {"action": "discard", "tiles": [tile]})
            self.state.log("action", {"login": self.login, "action": "discard", "tile": tile})
            return

        if phase == "claim" and actions:
            key = ("claim", snapshot.get("round_no"), snapshot.get("wall_count"), legal.get("claim_tile"), self.seat, tuple(sorted(str(a) for a in actions)))
            if self.last_key == key:
                return
            self.last_key = key
            if "hu" in actions:
                await self.send("game.action", {"action": "hu"})
                self.state.log(
                    "action",
                    {
                        "login": self.login,
                        "action": "hu",
                        "claim_tile": legal.get("claim_tile"),
                        "staged": True,
                    },
                )
                return
            await self.send("game.action", {"action": "pass"})
            self.state.log(
                "action",
                {
                    "login": self.login,
                    "action": "pass",
                    "options": actions,
                    "claim_tile": legal.get("claim_tile"),
                },
            )


class RunState:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.ready: dict = {}
        self.settled_payload: dict | None = None
        self.finished_payload: dict | None = None
        self.room_closed_payload: dict | None = None
        self.settled_event = asyncio.Event()

    def log(self, kind: str, data: dict) -> None:
        # 证据只留前 1500 条动作，避免荒庄连发把 JSON 撑爆
        if len(self.events) < 1500:
            self.events.append({"kind": kind, **data})

    def settle(self, data: dict) -> None:
        if self.settled_payload is None:
            payload = data.get("result") if isinstance(data.get("result"), dict) else data
            self.settled_payload = payload
            self.settled_event.set()

    def game_finished(self, data: dict) -> None:
        self.finished_payload = data

    def room_closed(self, data: dict) -> None:
        self.room_closed_payload = data


async def main(out_path: str) -> int:
    report: dict = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": []}

    def check(name: str, ok: bool, detail=None) -> None:
        report["checks"].append({"check": name, "pass": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail is not None else ""))

    status, created = http("POST", "/api/rooms", {"family_code": FAMILY_CODE, "room_name": ROOM_NAME, "template_id": TEMPLATE_ID, "circles": 1})
    check("开柏氏桌（POST /api/rooms, circles=1）", status == 200, {"status": status, "room": created if status != 200 else {"id": created.get("id"), "code": created.get("room_code"), "rule": created.get("rule_name")}})
    if status != 200:
        report["created"] = created
        Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    room_id = created["id"]
    room_code = created["room_code"]
    report["room"] = {"id": room_id, "code": room_code, "name": created.get("room_name"), "rule": created.get("rule_name")}

    state = RunState()
    bots = [Bot(login, room_code, state) for login in LOGINS]
    tasks = [asyncio.create_task(bot.run()) for bot in bots]

    # 等 4 人全部 ready，再开局
    for _ in range(100):
        await asyncio.sleep(0.2)
        if state.ready and all(state.ready.get(seat) for seat in range(4)):
            break
    check("四人入座并准备", all(state.ready.get(seat) for seat in range(4)), dict(state.ready))

    await bots[0].send("game.start")
    try:
        await asyncio.wait_for(state.settled_event.wait(), timeout=120)
    except asyncio.TimeoutError:
        pass

    settled = state.settled_payload or {}
    check("打满 1 局（收到 event.settled）", bool(settled), {k: settled.get(k) for k in ("round_no", "winner_seat", "win_type", "winning_tile", "fan_total", "pattern_id", "is_draw")})
    fan_items = settled.get("fan_items") or []
    report["settled"] = settled
    print("fan_items:", json.dumps(fan_items, ensure_ascii=False))

    # 结束牌局（房主）
    await bots[0].send("game.finish")
    for _ in range(60):
        await asyncio.sleep(0.2)
        if state.room_closed_payload is not None:
            break
    check("结束牌局 -> event.game_finished", state.finished_payload is not None, {k: (state.finished_payload or {}).get(k) for k in ("scores", "final", "aborted")})
    check("结束牌局 -> event.room_closed", state.room_closed_payload is not None, state.room_closed_payload)

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    # 大厅列表不含该房
    status, rooms = http("GET", "/api/rooms")
    codes = [item.get("room_code") for item in rooms] if isinstance(rooms, list) else rooms
    check("大厅列表不含该房（GET /api/rooms）", status == 200 and isinstance(rooms, list) and room_code not in codes, {"status": status, "codes": codes})

    # 重复关桌幂等
    status1, body1 = http("POST", f"/api/rooms/{room_id}/close")
    status2, body2 = http("POST", f"/api/rooms/{room_id}/close")
    check("重复关桌幂等（两次 POST /close）", status1 in (200, 201) and status2 in (200, 201), {"first": status1, "second": status2, "body2": body2 if status2 != 200 else body2.get("status")})

    report["room_after_close"] = body1 if isinstance(body1, dict) else str(body1)
    report["events"] = state.events
    report["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    report["all_pass"] = all(item["pass"] for item in report["checks"])
    Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all_pass": report["all_pass"], "room": report["room"]}, ensure_ascii=False))
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/home/codeops/mj_deploy2/smoke_evidence.json"
    sys.exit(asyncio.run(main(target)))
