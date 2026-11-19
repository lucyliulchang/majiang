"""v1.2.0 围观点名冒烟（测试服）：4 人入座 + 第 5 人围观，验证席位点名下发。

只走公开协议（REST 开桌 + WS 入座/观战/收桌），不改代码。
用法：sudo /usr/bin/python3 /tmp/spectate_smoke.py
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
ENV = {}
for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    ENV[key.strip()] = value.strip().strip('"').strip("'")

SECRET = ENV["SECRET_KEY"]
BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000/ws"
FAMILY_CODE = "s10jia"
TEMPLATE_ID = 1
ROOM_NAME = "v1.2.0 围观点名冒烟"
LOGINS = ["13800010001", "13800010002", "13800010003", "13800010004"]
VIEWER = "13800010006"
HOST = LOGINS[0]


def token(login):
    now = int(time.time())
    return jwt.encode(
        {"sub": login, "role": "member", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm="HS256",
    )


def http(method, path, payload=None, who=HOST):
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


class Client:
    def __init__(self, login, code):
        self.login = login
        self.url = f"{WS_BASE}?token={token(login)}&code={code}"
        self.messages = []
        self.ws = None
        self.reader = None

    async def start(self):
        self.ws = await websockets.connect(self.url, max_size=8 * 1024 * 1024)
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        try:
            async for raw in self.ws:
                self.messages.append(json.loads(raw))
        except Exception:
            pass

    def find(self, msg_type, pred=None):
        for msg in reversed(self.messages):
            if msg.get("type") != msg_type:
                continue
            data = msg.get("data") or {}
            if pred is None or pred(data):
                return data
        return None

    async def wait(self, msg_type, timeout=10.0, pred=None):
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self.find(msg_type, pred)
            if data is not None:
                return data
            await asyncio.sleep(0.1)
        return None

    async def send(self, msg_type, data=None):
        await self.ws.send(json.dumps({"type": msg_type, "data": data or {}}))

    async def stop(self):
        if self.reader:
            self.reader.cancel()
        await self.ws.close()


def seat_of(snapshot, login):
    for seat in snapshot.get("seats") or []:
        if seat and seat.get("login_id") == login:
            return seat.get("seat")
    return None


async def main() -> int:
    results = []

    def check(name, ok, detail=None):
        results.append((name, bool(ok), detail))
        print(("[PASS] " if ok else "[FAIL] ") + name + (f" -> {detail}" if detail is not None else ""))

    status, created = http(
        "POST",
        "/api/rooms",
        {"family_code": FAMILY_CODE, "room_name": ROOM_NAME, "template_id": TEMPLATE_ID, "circles": 1},
    )
    if status != 200:
        print("开桌失败", status, created)
        return 1
    room_id = created["id"]
    code = created["room_code"]
    print("room", room_id, code)

    clients = []
    try:
        for login in LOGINS:
            client = Client(login, code)
            await client.start()
            clients.append(client)
            welcome = await client.wait("room.welcome", timeout=10)
            check(f"{login} 入座", bool(welcome) and welcome.get("self_seat") is not None, (welcome or {}).get("self_seat"))
            await asyncio.sleep(0.3)

        host_snapshot = await clients[0].wait("state.snapshot", timeout=10, pred=lambda d: bool(d.get("seats")))
        seats = (host_snapshot or {}).get("seats") or []
        target_seat = seat_of(host_snapshot or {}, HOST)
        check("四座已满", len(seats) == 4 and all(seat is not None for seat in seats), [(s or {}).get("login_id") for s in seats])

        viewer = Client(VIEWER, code)
        await viewer.start()
        clients.append(viewer)
        welcome = await viewer.wait("room.welcome", timeout=10)
        check("第 5 人进桌且无座位（围观）", bool(welcome) and welcome.get("self_seat") is None, (welcome or {}).get("self_seat"))

        await viewer.send("spectate.target", {"seat": target_seat})
        snap = await viewer.wait("state.snapshot", timeout=10, pred=lambda d: bool(d.get("spectate")))
        view = (snap or {}).get("spectate") or {}
        check("观战者绑定目标", view.get("target_seat") == target_seat, view)

        seat_view = ((snap or {}).get("seats") or [])[target_seat] if snap else {}
        seat_view = seat_view or {}
        check(
            "观战者快照带点名（前两位）",
            seat_view.get("spectator_names") == ["访客"],
            {"names": seat_view.get("spectator_names"), "count": seat_view.get("spectator_count")},
        )
        check("人数仍按真实名额", seat_view.get("spectator_count") == 1, seat_view.get("spectator_count"))

        event = await clients[0].wait("event.spectate_changed", timeout=10, pred=lambda d: bool(d.get("seat_spectator_names")))
        names = (event or {}).get("seat_spectator_names")
        check("房主收到 event 点名", isinstance(names, list) and (names[target_seat] if names else None) == ["访客"], names)

        await clients[0].send("state.resync")
        host_snap = await clients[0].wait(
            "state.snapshot",
            timeout=10,
            pred=lambda d: (((d.get("seats") or [])[target_seat] or {}).get("spectator_count") == 1),
        )
        host_seat = (((host_snap or {}).get("seats") or [])[target_seat] or {}) if host_snap else {}
        check("房主快照也带点名（重连可恢复）", host_seat.get("spectator_names") == ["访客"], host_seat.get("spectator_names"))
    finally:
        for client in clients:
            try:
                await client.stop()
            except Exception:
                pass
        status, _ = http("POST", f"/api/rooms/{room_id}/close")
        print("close", status)

    ok = all(item[1] for item in results)
    print(json.dumps({"all_pass": ok, "total": len(results), "failed": [n for n, o, _ in results if not o]}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
