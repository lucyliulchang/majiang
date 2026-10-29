"""房间演员（RoomActor）：座位、连接、状态锁、事件广播、超时调度、聊天。

单进程内存 + asyncio.Lock 串行化所有状态变更，家庭规模（<10 并发）无需 Redis。

S5 口径：
  - 身份统一用 `loginID`（04 §11：user_id(int) → login_id(string)）；
  - 落库一律 `run_in_threadpool(persist.*)`：协程里绝不直接触库（01 §8.2）；
  - 落库失败不阻断对局（内存态优先），只记日志 + 给房主一条 `error{DB_WRITE_FAILED}`。
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.concurrency import run_in_threadpool

from config.localSettings import settings
from common.loggingCommon import get_logger
from game.engine import EngineError, GameEngine, SeatState, draw_seats
from game.families import registry
from game.tiles import tile_name
from realtime import persist
from realtime.snapshot import build_snapshot
from schemas.rule import RuleConfig
from schemas.ws import make_message

logger = get_logger("mahjong.room")


@dataclass
class PlayerSlot:
    seat: int
    login_id: str
    display_name: str
    color: str
    ready: bool = False
    connected: bool = True
    reserved_until: float = 0.0


@dataclass
class SpectateBinding:
    """观战绑定（一人一目标）。

    以 `target_login_id` 为准：抽座换座后按目标当前座位重算 `target_seat`，不会跟错人。
    `reserve_until` 在连接全断后生效，到期由 `_spectate_reserve` 释放名额。
    """

    target_login_id: str
    target_seat: int | None = None
    reserve_until: float = 0.0


@dataclass
class ChatBucket:
    stamps: list[float] = field(default_factory=list)

    def allow(self, window: int, limit: int) -> bool:
        now = time.time()
        self.stamps = [stamp for stamp in self.stamps if now - stamp < window]
        if len(self.stamps) >= limit:
            return False
        self.stamps.append(now)
        return True


class RoomActor:
    def __init__(
        self,
        code: str,
        room_id: int,
        family_id: int,
        family_code: str,
        family_name: str,
        name: str,
        host_login_id: str,
        rule: RuleConfig,
        rule_name: str,
        rule_snapshot: dict,
    ):
        self.code = code
        self.room_id = room_id
        self.family_id = family_id
        self.family_code = family_code
        self.family_name = family_name
        self.name = name
        self.host_login_id = host_login_id
        self.rule = rule
        self.rule_name = rule_name
        self.rule_snapshot = rule_snapshot
        self.rule_family_code = str((rule_snapshot or {}).get("rule_family_code") or "")

        self.slots: list[PlayerSlot | None] = [None, None, None, None]
        # 一个用户可以同时有多个连接（手机 + 电脑、或同一帐号开了两个标签页），
        # 因此按 loginID 维护连接列表：任一连接断开不得影响其余连接的推送。
        self.conns: dict[str, list[object]] = {}
        self.lock = asyncio.Lock()
        self.status = "waiting"
        self.engine: GameEngine | None = None
        self.game_id: int | None = None
        self.last_result: dict | None = None
        self.turn_deadline: float | None = None
        self.claim_deadline: float | None = None
        # 暂停（04 §9.4）：只有声明了 `pause` 开关的族可用；暂停期间冻结操作与倒计时
        self.paused = False
        self.paused_by_seat: int | None = None
        self.paused_by_login_id: str | None = None
        self.paused_note: str | None = None
        # 本场抽座结果（每场首局抽一次，圈内 4 局不重抽，03 §3.4）
        self.seat_draw: dict | None = None

        self._gen = 0
        self._turn_task: asyncio.Task | None = None
        self._claim_task: asyncio.Task | None = None
        self._chat_buckets: dict[str, ChatBucket] = defaultdict(ChatBucket)

        # 观战：loginID → 目标绑定；按 loginID 计数，多标签页只占 1 个名额
        self.spectators: dict[str, SpectateBinding] = {}
        self._spectate_tasks: dict[str, asyncio.Task] = {}

    # ---------------------------------------------------------------- 座位与连接
    def slot_of_login(self, login_id: str) -> PlayerSlot | None:
        for slot in self.slots:
            if slot and slot.login_id == login_id:
                return slot
        return None

    def first_free_seat(self) -> int | None:
        for seat, slot in enumerate(self.slots):
            if slot is None:
                return seat
        return None

    def seat_users(self) -> dict[int, str]:
        """座位 → loginID（落库与抽座共用）。"""
        return {slot.seat: slot.login_id for slot in self.slots if slot}

    def seat_of_login(self, login_id: str) -> int | None:
        """座位以下标为准（抽座时只换座位对象，不依赖 slot.seat 的旧值）。"""
        for seat, slot in enumerate(self.slots):
            if slot is not None and slot.login_id == login_id:
                return seat
        return None

    def player_count(self) -> int:
        return sum(1 for slot in self.slots if slot)

    def spectator_count(self) -> int:
        """在线但没座位的连接数（每个 loginID 只算一人）。"""
        seated = {slot.login_id for slot in self.slots if slot}
        return sum(1 for login_id in self.conns if login_id not in seated)

    # ---------------------------------------------------------------- 观战（S5b）
    def spectator_counts(self) -> list[int]:
        """按座位派生的围观计数 `[4]`；顺带刷新绑定里的 target_seat（抽座后自动跟随）。"""
        counts = [0, 0, 0, 0]
        for binding in self.spectators.values():
            seat = self.seat_of_login(binding.target_login_id)
            binding.target_seat = seat
            if seat is not None:
                counts[seat] += 1
        return counts

    def viewer_count_of(self, target_login_id: str) -> int:
        return sum(
            1 for binding in self.spectators.values() if binding.target_login_id == target_login_id
        )

    def spectate_count(self) -> int:
        """已占用的观战名额（按 loginID 计，不按连接数）。"""
        return sum(self.spectator_counts())

    def spectate_full(self) -> bool:
        """4 座满且 4×10 名额全满 → 握手必须拒绝（ROOM_SPECTATE_FULL/4005）。"""
        if self.player_count() < 4:
            return False
        return self.spectate_count() >= settings.spectate_room_max

    def spectate_of(self, login_id: str) -> dict | None:
        """该连接的观战视角（在座或未选目标返回 None）。"""
        binding = self.spectators.get(login_id)
        if binding is None:
            return None
        seat = self.seat_of_login(binding.target_login_id)
        binding.target_seat = seat
        return {
            "target_seat": seat,
            "target_login_id": binding.target_login_id,
            "viewer_count": self.viewer_count_of(binding.target_login_id),
            "limit_per_seat": settings.spectate_limit_per_seat,
        }

    def assign(self, login_id: str, display_name: str, color: str) -> PlayerSlot | None:
        existing = self.slot_of_login(login_id)
        if existing is not None:
            existing.connected = True
            existing.display_name = display_name
            existing.color = color
            return existing
        seat = self.first_free_seat()
        if seat is None:
            return None
        slot = PlayerSlot(
            seat=seat,
            login_id=login_id,
            display_name=display_name,
            color=color,
        )
        self.slots[seat] = slot
        return slot

    def attach(self, login_id: str, ws: object) -> None:
        conns = self.conns.setdefault(login_id, [])
        if ws not in conns:
            conns.append(ws)
        # 重连即取消观战保留计时，恢复原目标（不重复占名额）
        binding = self.spectators.get(login_id)
        if binding is not None:
            self._cancel_spectate_timer(login_id)
            binding.reserve_until = 0.0
            binding.target_seat = self.seat_of_login(binding.target_login_id)
            if binding.target_seat is None:
                self.spectators.pop(login_id, None)

    def _drop_conn(self, login_id: str, ws: object) -> None:
        conns = self.conns.get(login_id)
        if not conns:
            return
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.conns.pop(login_id, None)

    def detach(self, login_id: str, ws: object | None = None) -> None:
        """断开一个连接。仅当该用户已无任何连接时才标记座位离线并开始保留计时。

        观战绑定同样保留 `SPECTATE_RESERVE_SECONDS`：期间重连恢复原目标且不重复占位，
        到期由定时任务释放名额并广播（多标签页只算 1 个 loginID）。
        """
        if ws is None:
            self.conns.pop(login_id, None)
        else:
            self._drop_conn(login_id, ws)
        if login_id in self.conns:
            return
        slot = self.slot_of_login(login_id)
        if slot is not None:
            slot.connected = False
            slot.reserved_until = time.time() + settings.seat_reserve_seconds
            return
        binding = self.spectators.get(login_id)
        if binding is not None:
            seconds = settings.spectate_reserve_seconds
            binding.reserve_until = time.time() + seconds
            self._cancel_spectate_timer(login_id)
            self._spectate_tasks[login_id] = asyncio.create_task(
                self._spectate_reserve(login_id, seconds)
            )

    def _cancel_spectate_timer(self, login_id: str) -> None:
        task = self._spectate_tasks.pop(login_id, None)
        # 定时任务自己在释放名额时会走到这里，不能 cancel 当前任务
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()

    async def _spectate_reserve(self, login_id: str, seconds: int) -> None:
        await asyncio.sleep(max(0, seconds))
        async with self.lock:
            self._spectate_tasks.pop(login_id, None)
            if login_id in self.conns:
                return
            binding = self.spectators.get(login_id)
            if binding is None:
                return
            binding.target_seat = self.seat_of_login(binding.target_login_id)
            await self._release_spectate(login_id, broadcast=True)
            logger.info("观战名额保留到期释放 room=%s login=%s", self.code, login_id)

    # ---------------------------------------------------------------- 落库（线程池）
    async def _persist(self, func, *args):
        """把同步落库丢进线程池；失败只记日志并返回 None（不阻断对局，01 §7.4）。"""
        try:
            return await run_in_threadpool(func, *args)
        except Exception as error:  # noqa: BLE001 落库失败不能拖垮牌局
            logger.error(
                "落库失败 room=%s func=%s: %s",
                self.code,
                getattr(func, "__name__", str(func)),
                error,
            )
            return None

    async def _notifyWriteFailed(self) -> None:
        await self.send(
            self.host_login_id,
            make_message(
                "error", {"code": "DB_WRITE_FAILED", "message": "这局数据没存上，请稍后重试"}
            ),
        )

    # ---------------------------------------------------------------- 观战（S5b）
    async def _broadcast_spectate(self, target_login_id: str) -> None:
        """广播围观名额变化：全房可见计数，但不暴露观战者身份。"""
        seat = self.seat_of_login(target_login_id)
        payload = {
            "target_login_id": target_login_id,
            "target_seat": seat,
            "viewer_count": self.viewer_count_of(target_login_id) if seat is not None else 0,
            "seat_viewer_counts": self.spectator_counts(),
        }
        await self.broadcast(make_message("event.spectate_changed", payload))

    async def _release_spectate(self, login_id: str, broadcast: bool = True) -> bool:
        binding = self.spectators.pop(login_id, None)
        self._cancel_spectate_timer(login_id)
        if binding is None:
            return False
        if broadcast:
            await self._broadcast_spectate(binding.target_login_id)
        return True

    async def set_spectate_target(self, login_id: str, seat) -> None:
        """选择/切换/取消观战目标（04 §9.3）。

        名额转移在同一把锁内完成（调用方已持锁）：先释放旧目标，再占用新目标。
        目标满员时保持原绑定不动，只回 SPECTATE_TARGET_FULL。
        """
        if self.slot_of_login(login_id) is not None:
            await self.send_error(login_id, "SPECTATE_NOT_ALLOWED", "你在座，不能观战")
            return

        if seat is None:
            released = await self._release_spectate(login_id, broadcast=True)
            if released:
                await self._push_snapshot(login_id)
            else:
                await self.send_error(login_id, "SPECTATE_TARGET_INVALID", "你还没有选择观战对象")
            return

        try:
            target_seat = int(seat)
        except (TypeError, ValueError):
            target_seat = -1
        if target_seat < 0 or target_seat > 3:
            await self.send_error(login_id, "SPECTATE_TARGET_INVALID", "这个座位不存在")
            return
        target = self.slots[target_seat]
        if target is None:
            await self.send_error(login_id, "SPECTATE_TARGET_INVALID", "这个位置还没人，换一个吧")
            return

        existing = self.spectators.get(login_id)
        if existing is not None and existing.target_login_id == target.login_id:
            # 同一目标重复提交：幂等，只补发一次快照
            await self._push_snapshot(login_id)
            return

        used = sum(
            1
            for viewer, binding in self.spectators.items()
            if viewer != login_id and binding.target_login_id == target.login_id
        )
        if used >= settings.spectate_limit_per_seat:
            await self.send_error(
                login_id,
                "SPECTATE_TARGET_FULL",
                f"该玩家已有 {settings.spectate_limit_per_seat} 人围观，请选择其他玩家",
            )
            return

        old_target = existing.target_login_id if existing is not None else ""
        self.spectators[login_id] = SpectateBinding(
            target_login_id=target.login_id, target_seat=target_seat
        )
        self._cancel_spectate_timer(login_id)
        if old_target:
            await self._broadcast_spectate(old_target)
        await self._broadcast_spectate(target.login_id)
        await self._push_snapshot(login_id)
        logger.info(
            "观战切换 room=%s login=%s target=%s(%s)", self.code, login_id, target.login_id, target_seat
        )

    async def drop_spectate(self, login_id: str) -> None:
        """该用户重新入座时释放观战绑定（同一 loginID 不能既在座又占围观名额）。"""
        if await self._release_spectate(login_id, broadcast=True):
            await self._push_snapshot(login_id)

    async def clear_seat(self, seat: int) -> None:
        """座位被回收/玩家离座：清空该目标的观战者并广播 target_seat=null。"""
        slot = self.slots[seat]
        if slot is None:
            return
        target_login_id = slot.login_id
        self.slots[seat] = None
        affected = [
            viewer
            for viewer, binding in self.spectators.items()
            if binding.target_login_id == target_login_id
        ]
        for viewer in affected:
            self.spectators.pop(viewer, None)
            self._cancel_spectate_timer(viewer)
        await self.broadcast(
            make_message(
                "event.spectate_changed",
                {
                    "target_login_id": target_login_id,
                    "target_seat": None,
                    "viewer_count": 0,
                    "seat_viewer_counts": self.spectator_counts(),
                },
            )
        )
        for viewer in affected:
            await self._push_snapshot(viewer)
        await self.push_all()

    def forget_spectators(self) -> None:
        """同步丢绑定（演员销毁时调用，此时连接已无需通知）。"""
        for login_id in list(self.spectators):
            self._cancel_spectate_timer(login_id)
        self.spectators.clear()

    async def close_spectate(self) -> None:
        """房间关闭：释放全部观战绑定（内存态，无库操作）。"""
        for login_id in list(self.spectators):
            self._cancel_spectate_timer(login_id)
        if not self.spectators:
            return
        self.spectators.clear()
        await self.broadcast(
            make_message(
                "event.spectate_changed",
                {
                    "target_login_id": "",
                    "target_seat": None,
                    "viewer_count": 0,
                    "seat_viewer_counts": [0, 0, 0, 0],
                },
            )
        )

    # ---------------------------------------------------------------- 发送
    async def send(self, login_id: str, message: dict) -> None:
        conns = self.conns.get(login_id)
        if not conns:
            return
        for ws in list(conns):
            try:
                await ws.send_json(message)
            except (RuntimeError, ConnectionError) as error:  # 连接已断，静默清理
                logger.warning(
                    "发送失败，连接可能已断开 room=%s login=%s: %s", self.code, login_id, error
                )
                self._drop_conn(login_id, ws)

    async def send_error(self, login_id: str, code: str, message: str) -> None:
        await self.send(login_id, make_message("error", {"code": code, "message": message}))

    async def broadcast(self, message: dict, exclude: str | None = None) -> None:
        for login_id in list(self.conns.keys()):
            if login_id == exclude:
                continue
            await self.send(login_id, message)

    async def push_all(self) -> None:
        for login_id in list(self.conns.keys()):
            await self._push_snapshot(login_id)

    async def _push_snapshot(self, login_id: str) -> None:
        slot = self.slot_of_login(login_id)
        viewer = slot.seat if slot is not None else None
        await self.send(
            login_id, make_message("state.snapshot", build_snapshot(self, viewer, login_id))
        )

    async def system_chat(self, content: str) -> None:
        record = await self._persist(
            persist.save_message, self.room_id, self.family_id, None, "system", content
        )
        if record is None:
            await self._notifyWriteFailed()
            return
        await self.broadcast(make_message("chat.message", record))

    # ---------------------------------------------------------------- 消息入口
    async def handle(self, login_id: str, message: dict) -> None:
        msg_type = message.get("type")
        data = message.get("data") or {}
        if msg_type == "ping":
            await self.send(login_id, make_message("pong"))
            return
        async with self.lock:
            if msg_type == "state.resync":
                await self.push_all()
            elif msg_type == "spectate.target":
                await self.set_spectate_target(login_id, data.get("seat"))
            elif msg_type == "seat.ready":
                await self._toggle_ready(login_id)
            elif msg_type == "game.start":
                await self._start_game(login_id)
            elif msg_type == "game.next":
                await self._next_round(login_id)
            elif msg_type == "game.action":
                await self._action(login_id, data)
            elif msg_type == "room.pause":
                await self._set_paused(login_id, True, data.get("note"))
            elif msg_type == "room.resume":
                await self._set_paused(login_id, False, data.get("note"))
            elif msg_type == "chat.send":
                await self._chat(login_id, data)
            else:
                await self.send_error(login_id, "UNKNOWN_TYPE", f"不认识的消息类型：{msg_type}")

    # ---------------------------------------------------------------- 暂停
    def _pause_supported(self) -> bool:
        """暂停是族能力（03 §2.2 `switches` 含 `pause`），不支持就不接这条消息。"""
        pause = getattr(self.rule, "pause", None)
        return bool(getattr(pause, "enabled", False))

    async def _set_paused(self, login_id: str, paused: bool, note=None) -> None:
        """`room.pause` / `room.resume`（04 §9.4）：暂停期间冻结一切倒计时与操作。"""
        slot = self.slot_of_login(login_id)
        if slot is None:
            await self.send_error(login_id, "NO_SEAT", "你在观战，不能暂停牌局")
            return
        if not self._pause_supported():
            await self.send_error(login_id, "PAUSE_UNSUPPORTED", "当前规则族不支持暂停")
            return
        if self.status != "playing" or self.engine is None or self.engine.phase == "settled":
            await self.send_error(login_id, "NOT_PLAYING", "牌局还没开始或本局已结束")
            return
        if paused == self.paused:
            await self.send_error(
                login_id,
                "PAUSE_UNCHANGED",
                "牌局已经暂停" if paused else "牌局没有暂停",
            )
            return

        self.paused = paused
        self.paused_by_seat = slot.seat if paused else None
        self.paused_note = (str(note).strip()[:60] or None) if paused else None
        self.paused_by_login_id = login_id if paused else None
        if paused:
            self._clear_timers()
            self.turn_deadline = None
            self.claim_deadline = None
        else:
            # 恢复后重开当前阶段的计时（暂停期间不累计进度）
            self._sync_timers()
        await self.broadcast(
            make_message(
                "event.paused",
                {
                    "paused": paused,
                    "by_seat": self.paused_by_seat,
                    "by_name": slot.display_name if paused else None,
                    "note": self.paused_note,
                },
            )
        )
        await self.system_chat(
            f"{slot.display_name} {'暂停了牌局' if paused else '恢复了牌局'}"
            + (f"（{self.paused_note}）" if self.paused_note else "")
        )
        await self.push_all()

    async def _toggle_ready(self, login_id: str) -> None:
        slot = self.slot_of_login(login_id)
        if slot is None:
            await self.send_error(login_id, "NO_SEAT", "你还在观战，没有座位")
            return
        slot.ready = not slot.ready
        await self.broadcast(
            make_message("event.ready_changed", {"seat": slot.seat, "ready": slot.ready})
        )
        await self.push_all()

    async def _start_game(self, login_id: str) -> None:
        if self.slot_of_login(login_id) is None:
            await self.send_error(login_id, "NO_SEAT", "你在观战，不能开局")
            return
        if login_id != self.host_login_id:
            await self.send_error(login_id, "NOT_HOST", "只有房主可以开桌")
            return
        if self.status == "playing" and self.engine and self.engine.phase != "settled":
            await self.send_error(login_id, "PLAYING", "牌局正在进行中")
            return
        filled = [slot for slot in self.slots if slot is not None]
        if len(filled) < 4:
            await self.send_error(login_id, "NOT_ENOUGH", "还差人，需要 4 位玩家都入座")
            return
        if not all(slot.ready for slot in filled):
            await self.send_error(login_id, "NOT_READY", "还有玩家没有点准备")
            return
        await self._begin_game()

    async def _begin_game(self) -> None:
        # 每场首局抽座一次：掷骰定东位/庄家并广播 event.seats_drawn（03 §3.4）
        draw = draw_seats([slot.login_id for slot in self.slots if slot is not None])
        await self._apply_seat_draw(draw)

        seats = [
            SeatState(
                seat=index,
                login_id=slot.login_id,
                display_name=slot.display_name,
                color=slot.color,
            )
            for index, slot in enumerate(self.slots)
            if slot is not None
        ]
        self.engine = registry.create_engine(self.rule_family_code or "generic", self.rule, seats, round_no=1)
        # 抽座记录落库（mj_game.seatDrawJson）：便于复现「谁掷了多少点」
        self.seat_draw = draw
        # 开局落库：game + 4 条 player 同一事务；失败也不阻止打牌（内存态优先）
        rows = [
            (slot.seat, slot.login_id, slot.display_name)
            for slot in self.slots
            if slot is not None
        ]
        self.game_id = await self._persist(
            persist.open_game,
            self.room_id,
            self.family_id,
            self.rule_snapshot.get("rule_family_code", ""),
            self.rule_snapshot,
            rows,
            draw,
        )
        if self.game_id is None:
            await self._notifyWriteFailed()
        self.status = "playing"
        self.last_result = None
        self.paused = False
        self.paused_by_seat = None
        self.paused_by_login_id = None
        self.paused_note = None
        logger.info("开桌 room=%s game=%s dealer=%s", self.code, self.game_id, draw["dealer_seat"])
        await self._after(self.engine.start_round())

    async def _apply_seat_draw(self, draw: dict) -> None:
        """按抽座结果重排物理座位，并广播 `event.seats_drawn`。

        座位号 0/1/2/3 是物理座位（0 = 东位）；抽座后座位对象整体换位，
        观战绑定按 loginID 跟随，不跟错人（`spectator_counts()` 会重算 target_seat）。
        """
        byLogin = {slot.login_id: slot for slot in self.slots if slot is not None}
        newSlots: list[PlayerSlot | None] = [None, None, None, None]
        for entry in draw["assignments"]:
            slot = byLogin.get(entry["login_id"])
            if slot is None:
                continue
            slot.seat = int(entry["seat"])
            newSlots[slot.seat] = slot
        self.slots = newSlots
        await self.broadcast(
            make_message(
                "event.seats_drawn",
                {
                    "assignments": [
                        {
                            "seat": int(entry["seat"]),
                            "login_id": entry["login_id"],
                            "dice": list(entry["dice"]),
                        }
                        for entry in draw["assignments"]
                    ],
                    "dealer_seat": int(draw["dealer_seat"]),
                    "round_no": 1,
                    "seat_viewer_counts": self.spectator_counts(),
                },
            )
        )

    async def _next_round(self, login_id: str) -> None:
        if self.slot_of_login(login_id) is None:
            await self.send_error(login_id, "NO_SEAT", "你在观战，不能开局")
            return
        if self.engine is None:
            await self.send_error(login_id, "NOT_STARTED", "牌局还没开始")
            return
        if self.engine.phase != "settled":
            await self.send_error(login_id, "NOT_SETTLED", "本局还没结束")
            return
        if login_id != self.host_login_id:
            await self.send_error(login_id, "NOT_HOST", "只有房主可以开始下一局")
            return
        if self.engine.round_no >= self.rule.rounds_per_game:
            await self._finish_game()
            return
        for slot in self.slots:
            if slot is not None:
                slot.ready = True
        # 轮庄与局风全由局号推导：第 n 局庄家 = 座位 n-1，局风 东→南→西→北（03 §3.4）。
        # 无杠重发在同一局内由引擎自行处理（不发 game.next），因此这里只推进局号。
        roundNo = self.engine.round_no + 1
        self.engine = registry.create_engine(
            self.rule_family_code or "generic",
            self.rule,
            list(self.engine.seats.values()),
            round_no=roundNo,
        )
        self.last_result = None
        await self._after(self.engine.start_round())

    async def _finish_game(self) -> None:
        if self.game_id is not None:
            await self._persist(persist.close_game, self.game_id)
        self.status = "finished"
        scores = [
            {"seat": slot.seat, "name": slot.display_name, "total": 0}
            for slot in self.slots
            if slot is not None
        ]
        if self.engine is not None:
            for entry in scores:
                entry["total"] = self.engine.seats[entry["seat"]].total_score
        await self.broadcast(make_message("event.game_finished", {"scores": scores}))
        await self.push_all()

    async def _action(self, login_id: str, data: dict) -> None:
        slot = self.slot_of_login(login_id)
        if slot is None:
            await self.send_error(login_id, "NO_SEAT", "你在观战，不能操作牌局")
            return
        if self.engine is None or self.engine.phase == "settled":
            await self.send_error(login_id, "NOT_PLAYING", "牌局还没开始或本局已结束")
            return
        if self.paused:
            await self.send_error(login_id, "ROOM_PAUSED", "牌局已暂停，恢复后才能继续操作")
            return
        action = {
            "action": data.get("action"),
            "tiles": data.get("tiles") or [],
            "kong_kind": data.get("kong_kind"),
        }
        try:
            events = self.engine.apply_action(slot.seat, action)
        except EngineError as error:
            await self.send_error(login_id, error.code, error.message)
            return
        await self._after(events)

    # ---------------------------------------------------------------- 聊天
    async def _chat(self, login_id: str, data: dict) -> None:
        content = str(data.get("content", "")).strip()
        if not content:
            await self.send_error(login_id, "EMPTY_CHAT", "消息不能为空")
            return
        if len(content) > 200:
            await self.send_error(login_id, "CHAT_TOO_LONG", "消息最多 200 个字")
            return
        if not self._chat_buckets[login_id].allow(
            settings.chat_rate_window, settings.chat_rate_limit
        ):
            await self.send_error(login_id, "CHAT_TOO_FAST", "说太快啦，歇一下再说")
            return
        slot = self.slot_of_login(login_id)
        name = slot.display_name if slot else "观战者"
        record = await self._persist(
            persist.save_message, self.room_id, self.family_id, login_id, "chat", content
        )
        if record is None:
            await self.send_error(login_id, "DB_WRITE_FAILED", "消息没发出去，请重试")
            return
        record["user_name"] = name
        await self.broadcast(make_message("chat.message", record))

    # ---------------------------------------------------------------- 状态推进
    async def _after(self, events: list[dict]) -> None:
        for event in events:
            await self.broadcast(make_message(event["type"], event["data"]))
        await self.push_all()
        if self.engine is not None and self.engine.phase == "settled":
            await self._on_settled()
            return
        # 无杠荒庄 → 重发本局：给牌桌留一句系统提示，避免家人以为卡住了（03 §3.6）
        if any(event["type"] == "event.round_restarted" for event in events):
            await self.system_chat("牌墙摸尽且本局无人杠，重新发牌（第 %d 局不计）" % self.engine.round_no)
        self._sync_timers()

    async def _on_settled(self) -> None:
        self._clear_timers()
        self.turn_deadline = None
        self.claim_deadline = None
        engine = self.engine
        if engine is None or engine.result is None:
            return
        settled = engine.result
        self.last_result = {
            "round_no": settled.round_no,
            "dealer_seat": settled.dealer_seat,
            "round_wind": settled.round_wind,
            "winner_seat": settled.winner_seat,
            "win_type": settled.win_type,
            "winning_tile": settled.winning_tile,
            "pattern_id": settled.pattern_id,
            "fan_total": settled.fan_total,
            "fan_items": settled.fan_items,
            "score_delta": settled.score_delta,
            "breakdown": settled.breakdown,
            "is_last_round": settled.round_no >= self.rule.rounds_per_game,
            # S6 追加（04 §9.5 的 result 结构，只增字段不删字段）
            "winners": settled.winners,
            "fan_raw": settled.fan_raw,
            "fan_cap": settled.fan_cap,
            "kong_delta": settled.kong_delta,
            # S7 追加：包牌/倍数付款方分配（四川血战与柏氏包牌会用到）
            "payer_allocation": list(settled.payer_allocation),
            "multipliers": dict(settled.multipliers),
            "summary_text": settled.summary_text,
            "is_draw": settled.is_draw,
        }
        if self.game_id is not None:
            saved = await self._persist(
                persist.save_round, self.game_id, self.family_id, settled
            )
            if saved is None:
                await self._notifyWriteFailed()
        logger.info(
            "结算 room=%s round=%s winner=%s fan=%s delta=%s kong=%s",
            self.code,
            settled.round_no,
            settled.winner_seat,
            settled.fan_total,
            settled.score_delta,
            self.rule.kong_score.enabled,
        )
        winners = settled.winners
        if len(winners) > 1:
            # 四川血战：一局多个赢家，逐个点名（事件协议不变，只是文案更完整）
            parts = []
            for item in winners:
                seat = int(item.get("seat", 0))
                name = self.engine.seats[seat].display_name
                parts.append(
                    f"{name}{'自摸' if item.get('win_type') == 'self_draw' else '胡'}"
                    f" {item.get('fan_total', 0)} 番"
                )
            text = "多人胡牌：" + "、".join(parts)
        elif settled.winner_seat is not None:
            text = (
                f"{self.engine.seats[settled.winner_seat].display_name} "
                f"{'自摸' if settled.win_type == 'self_draw' else '胡牌'}"
                f"（{tile_name(settled.winning_tile) if settled.winning_tile is not None else '荒庄'}）"
                f"，{settled.fan_total} 番"
            )
            if settled.summary_text:
                text += f" · {settled.summary_text}"
            for allocation in settled.payer_allocation:
                if allocation.get("reason") == "bao_pai":
                    payer = int(allocation.get("bao_pai_seat", 0))
                    text += f" · 包牌：{self.engine.seats[payer].display_name}独付"
        elif engine.kong_happened:
            text = "荒庄（本局有杠），本局计局并迁庄"
        else:
            text = "荒庄，本局无人胡牌"
        await self.system_chat(text)
        await self.push_all()

    def _sync_timers(self) -> None:
        self._clear_timers()
        engine = self.engine
        if engine is None:
            return
        if self.paused:
            # 暂停期间冻结一切倒计时（04 §9.4），恢复时再按当前阶段重开
            self.turn_deadline = None
            self.claim_deadline = None
            return
        self._gen += 1
        gen = self._gen
        now = time.time()
        if engine.phase == "claim":
            self.claim_deadline = now + self.rule.claim_window_seconds
            self.turn_deadline = None
            self._claim_task = asyncio.create_task(
                self._claim_timeout(gen, self.rule.claim_window_seconds)
            )
        elif engine.phase == "discard" and getattr(self.rule.turn_timeout, "enabled", False):
            seconds = self.rule.turn_timeout.seconds
            self.turn_deadline = now + seconds
            self.claim_deadline = None
            self._turn_task = asyncio.create_task(self._turn_timeout(gen, seconds))
        else:
            self.turn_deadline = None
            self.claim_deadline = None

    def _clear_timers(self) -> None:
        for task in (self._turn_task, self._claim_task):
            if task is not None and not task.done():
                task.cancel()
        self._turn_task = None
        self._claim_task = None

    async def _claim_timeout(self, gen: int, seconds: int) -> None:
        await asyncio.sleep(seconds)
        if gen != self._gen:
            return
        async with self.lock:
            if gen != self._gen or self.engine is None:
                return
            self._claim_task = None
            events = self.engine.timeout_claim()
            if not events:
                return
            await self.broadcast(make_message("event.claim_timeout", {"message": "超时未响应，按过处理"}))
            await self._after(events)

    async def _turn_timeout(self, gen: int, seconds: int) -> None:
        await asyncio.sleep(seconds)
        if gen != self._gen:
            return
        async with self.lock:
            if gen != self._gen or self.engine is None:
                return
            engine = self.engine
            if engine.phase != "discard":
                return
            self._turn_task = None
            state = engine.seats[engine.turn]
            tile = None
            if engine.last_draw is not None and state.counts[engine.last_draw] > 0:
                tile = engine.last_draw
            else:
                for index, count in enumerate(state.counts):
                    if count > 0:
                        tile = index
                        break
            if tile is None:
                return
            await self.broadcast(
                make_message(
                    "event.auto_discard",
                    {"seat": engine.turn, "message": "超时未出牌，系统自动打出"},
                )
            )
            try:
                events = engine.apply_action(engine.turn, {"action": "discard", "tiles": [tile]})
            except EngineError as error:
                logger.warning("自动出牌失败 room=%s: %s", self.code, error.message)
                return
            await self._after(events)
