"""房间演员（RoomActor）：座位、连接、状态锁、事件广播、超时调度、聊天。

单进程内存 + asyncio.Lock 串行化所有状态变更，家庭规模（<10 并发）无需 Redis。
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field

from config.localSettings import settings
from common.loggingCommon import get_logger
from game.engine import EngineError, GameEngine, SeatState
from game.tiles import tile_name
from realtime import persist
from realtime.snapshot import build_snapshot
from schemas.rule import RuleConfig
from schemas.ws import make_message

logger = get_logger("mahjong.room")


@dataclass
class PlayerSlot:
    seat: int
    user_id: int
    display_name: str
    color: str
    ready: bool = False
    connected: bool = True
    reserved_until: float = 0.0


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
        name: str,
        host_id: int,
        rule: RuleConfig,
        rule_name: str,
        rule_snapshot: dict,
    ):
        self.code = code
        self.room_id = room_id
        self.name = name
        self.host_id = host_id
        self.rule = rule
        self.rule_name = rule_name
        self.rule_snapshot = rule_snapshot

        self.slots: list[PlayerSlot | None] = [None, None, None, None]
        # 一个用户可以同时有多个连接（手机 + 电脑、或同一帐号开了两个标签页），
        # 因此按 user_id 维护连接列表：任一连接断开不得影响其余连接的推送。
        self.conns: dict[int, list[object]] = {}
        self.lock = asyncio.Lock()
        self.status = "waiting"
        self.engine: GameEngine | None = None
        self.game_id: int | None = None
        self.last_result: dict | None = None
        self.turn_deadline: float | None = None
        self.claim_deadline: float | None = None

        self._gen = 0
        self._turn_task: asyncio.Task | None = None
        self._claim_task: asyncio.Task | None = None
        self._chat_buckets: dict[int, ChatBucket] = defaultdict(ChatBucket)

    # ---------------------------------------------------------------- 座位与连接
    def slot_of_user(self, user_id: int) -> PlayerSlot | None:
        for slot in self.slots:
            if slot and slot.user_id == user_id:
                return slot
        return None

    def first_free_seat(self) -> int | None:
        for seat, slot in enumerate(self.slots):
            if slot is None:
                return seat
        return None

    def seat_users(self) -> dict[int, int]:
        return {slot.seat: slot.user_id for slot in self.slots if slot}

    def assign(self, user) -> PlayerSlot | None:
        existing = self.slot_of_user(user.id)
        if existing is not None:
            existing.connected = True
            existing.display_name = user.display_name
            existing.color = user.color
            return existing
        seat = self.first_free_seat()
        if seat is None:
            return None
        slot = PlayerSlot(
            seat=seat,
            user_id=user.id,
            display_name=user.display_name,
            color=user.color,
        )
        self.slots[seat] = slot
        return slot

    def attach(self, user_id: int, ws: object) -> None:
        conns = self.conns.setdefault(user_id, [])
        if ws not in conns:
            conns.append(ws)

    def _drop_conn(self, user_id: int, ws: object) -> None:
        conns = self.conns.get(user_id)
        if not conns:
            return
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.conns.pop(user_id, None)

    def detach(self, user_id: int, ws: object | None = None) -> None:
        """断开一个连接。仅当该用户已无任何连接时才标记座位离线并开始保留计时。"""
        if ws is None:
            self.conns.pop(user_id, None)
        else:
            self._drop_conn(user_id, ws)
        if user_id in self.conns:
            return
        slot = self.slot_of_user(user_id)
        if slot is not None:
            slot.connected = False
            slot.reserved_until = time.time() + settings.seat_reserve_seconds

    # ---------------------------------------------------------------- 发送
    async def send(self, user_id: int, message: dict) -> None:
        conns = self.conns.get(user_id)
        if not conns:
            return
        for ws in list(conns):
            try:
                await ws.send_json(message)
            except (RuntimeError, ConnectionError) as error:  # 连接已断，静默清理
                logger.warning("发送失败，连接可能已断开 room=%s user=%s: %s", self.code, user_id, error)
                self._drop_conn(user_id, ws)

    async def send_error(self, user_id: int, code: str, message: str) -> None:
        await self.send(user_id, make_message("error", {"code": code, "message": message}))

    async def broadcast(self, message: dict, exclude: int | None = None) -> None:
        for user_id in list(self.conns.keys()):
            if user_id == exclude:
                continue
            await self.send(user_id, message)

    async def push_all(self) -> None:
        for user_id in list(self.conns.keys()):
            slot = self.slot_of_user(user_id)
            viewer = slot.seat if slot else None
            await self.send(user_id, make_message("state.snapshot", build_snapshot(self, viewer)))

    async def system_chat(self, content: str) -> None:
        record = persist.save_message(self.room_id, None, "system", content)
        await self.broadcast(make_message("chat.message", record))

    # ---------------------------------------------------------------- 消息入口
    async def handle(self, user_id: int, message: dict) -> None:
        msg_type = message.get("type")
        data = message.get("data") or {}
        if msg_type == "ping":
            await self.send(user_id, make_message("pong"))
            return
        async with self.lock:
            if msg_type == "state.resync":
                await self.push_all()
            elif msg_type == "seat.ready":
                await self._toggle_ready(user_id)
            elif msg_type == "game.start":
                await self._start_game(user_id)
            elif msg_type == "game.next":
                await self._next_round(user_id)
            elif msg_type == "game.action":
                await self._action(user_id, data)
            elif msg_type == "chat.send":
                await self._chat(user_id, data)
            else:
                await self.send_error(user_id, "UNKNOWN_TYPE", f"不认识的消息类型：{msg_type}")

    async def _toggle_ready(self, user_id: int) -> None:
        slot = self.slot_of_user(user_id)
        if slot is None:
            await self.send_error(user_id, "NO_SEAT", "你还在观战，没有座位")
            return
        slot.ready = not slot.ready
        await self.broadcast(
            make_message("event.ready_changed", {"seat": slot.seat, "ready": slot.ready})
        )
        await self.push_all()

    async def _start_game(self, user_id: int) -> None:
        if user_id != self.host_id:
            await self.send_error(user_id, "NOT_HOST", "只有房主可以开桌")
            return
        if self.status == "playing" and self.engine and self.engine.phase != "settled":
            await self.send_error(user_id, "PLAYING", "牌局正在进行中")
            return
        filled = [slot for slot in self.slots if slot is not None]
        if len(filled) < 4:
            await self.send_error(user_id, "NOT_ENOUGH", "还差人，需要 4 位玩家都入座")
            return
        if not all(slot.ready for slot in filled):
            await self.send_error(user_id, "NOT_READY", "还有玩家没有点准备")
            return
        await self._begin_game()

    async def _begin_game(self) -> None:
        seats = [
            SeatState(
                seat=slot.seat,
                user_id=slot.user_id,
                display_name=slot.display_name,
                color=slot.color,
            )
            for slot in self.slots
            if slot is not None
        ]
        self.engine = GameEngine(self.rule, seats, round_no=1, dealer_seat=0)
        self.game_id = persist.open_game(
            self.room_id, self.rule_snapshot, list(self.seat_users().items())
        )
        self.status = "playing"
        self.last_result = None
        logger.info("开桌 room=%s game=%s", self.code, self.game_id)
        await self._after(self.engine.start_round())

    async def _next_round(self, user_id: int) -> None:
        if self.engine is None:
            await self.send_error(user_id, "NOT_STARTED", "牌局还没开始")
            return
        if self.engine.phase != "settled":
            await self.send_error(user_id, "NOT_SETTLED", "本局还没结束")
            return
        if user_id != self.host_id:
            await self.send_error(user_id, "NOT_HOST", "只有房主可以开始下一局")
            return
        if self.engine.round_no >= self.rule.rounds_per_game:
            await self._finish_game()
            return
        for slot in self.slots:
            if slot is not None:
                slot.ready = True
        self.engine = GameEngine(
            self.rule,
            list(self.engine.seats.values()),
            round_no=self.engine.round_no + 1,
            dealer_seat=self.engine.next_dealer(),
        )
        self.last_result = None
        await self._after(self.engine.start_round())

    async def _finish_game(self) -> None:
        if self.game_id is not None:
            persist.close_game(self.game_id)
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

    async def _action(self, user_id: int, data: dict) -> None:
        slot = self.slot_of_user(user_id)
        if slot is None:
            await self.send_error(user_id, "NO_SEAT", "你在观战，不能操作牌局")
            return
        if self.engine is None or self.engine.phase == "settled":
            await self.send_error(user_id, "NOT_PLAYING", "牌局还没开始或本局已结束")
            return
        action = {
            "action": data.get("action"),
            "tiles": data.get("tiles") or [],
            "kong_kind": data.get("kong_kind"),
        }
        try:
            events = self.engine.apply_action(slot.seat, action)
        except EngineError as error:
            await self.send_error(user_id, error.code, error.message)
            return
        await self._after(events)

    # ---------------------------------------------------------------- 聊天
    async def _chat(self, user_id: int, data: dict) -> None:
        content = str(data.get("content", "")).strip()
        if not content:
            await self.send_error(user_id, "EMPTY_CHAT", "消息不能为空")
            return
        if len(content) > 200:
            await self.send_error(user_id, "CHAT_TOO_LONG", "消息最多 200 个字")
            return
        if not self._chat_buckets[user_id].allow(
            settings.chat_rate_window, settings.chat_rate_limit
        ):
            await self.send_error(user_id, "CHAT_TOO_FAST", "说太快啦，歇一下再说")
            return
        slot = self.slot_of_user(user_id)
        name = slot.display_name if slot else "观战者"
        record = persist.save_message(self.room_id, user_id, "chat", content)
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
            "winner_seat": settled.winner_seat,
            "win_type": settled.win_type,
            "winning_tile": settled.winning_tile,
            "pattern_id": settled.pattern_id,
            "fan_total": settled.fan_total,
            "fan_items": settled.fan_items,
            "score_delta": settled.score_delta,
            "breakdown": settled.breakdown,
            "is_last_round": settled.round_no >= self.rule.rounds_per_game,
        }
        if self.game_id is not None:
            persist.save_round(self.game_id, settled, self.seat_users())
        logger.info(
            "结算 room=%s round=%s winner=%s fan=%s delta=%s kong=%s",
            self.code,
            settled.round_no,
            settled.winner_seat,
            settled.fan_total,
            settled.score_delta,
            self.rule.kong_score.enabled,
        )
        if settled.winner_seat is not None:
            text = (
                f"{self.engine.seats[settled.winner_seat].display_name} "
                f"{'自摸' if settled.win_type == 'self_draw' else '胡牌'}"
                f"（{tile_name(settled.winning_tile) if settled.winning_tile is not None else '荒庄'}）"
                f"，{settled.fan_total} 番"
            )
        else:
            text = "荒庄，本局无人胡牌"
        await self.system_chat(text)
        await self.push_all()

    def _sync_timers(self) -> None:
        self._clear_timers()
        engine = self.engine
        if engine is None:
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
        elif engine.phase == "discard" and self.rule.turn_timeout.enabled:
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
