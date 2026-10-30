"""房间演员（RoomActor）：座位、连接、状态锁、事件广播、超时调度、聊天。

单进程内存 + asyncio.Lock 串行化所有状态变更，家庭规模（<10 并发）无需 Redis。

S5 口径：
  - 身份统一用 `loginID`（04 §11：user_id(int) → login_id(string)）；
  - 落库一律 `run_in_threadpool(persist.*)`：协程里绝不直接触库（01 §8.2）；
  - 落库失败不阻断对局（内存态优先），只记日志 + 给房主一条 `error{DB_WRITE_FAILED}`；
    例外是 `close_room` / `close_game` 这类**不可丢**的收尾写入（B-1）：失败必须上抛
    `PersistError`，由调用方回 `CLOSE_FAILED`，避免「内存已关、库里还开」的幽灵房。
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
from game.families.generic.config import CIRCLES_PER_GAME
from game.tiles import tile_name
from realtime import persist
from realtime.snapshot import build_snapshot, welcome_payload
from schemas.rule import RuleConfig
from schemas.ws import make_message

logger = get_logger("mahjong.room")

# 一圈固定 4 个庄次（北位下庄即本圈结束）；一场默认 4 圈，开桌时可按桌覆盖（v1.1.0）
ROUNDS_PER_CIRCLE = 4


def nextRoundState(
    dealerSeat: int,
    roundWind: int,
    circleNo: int,
    nextDealer: int,
    roundsPerCircle: int = ROUNDS_PER_CIRCLE,
    totalCircles: int = CIRCLES_PER_GAME,
) -> tuple[int, int, int, bool]:
    """下一局的 `(庄家座位, 局风, 圈序, 本场是否结束)`（纯函数，便于单测）。

    - 连庄（`nextDealer == dealerSeat`）：庄位与局风都不动，圈序不变；
    - 下庄：局风 +1；攒满一圈的 4 个庄次即本圈结束，圈序 +1 且局风回到东风；
    - 圈序超过 `totalCircles` 即本场收场。
    座位整场只抽一次，换圈不重抽，庄家照座位顺延（北位之后回到东位）。
    """
    if nextDealer == dealerSeat:
        return dealerSeat, roundWind, circleNo, False
    nextWind = roundWind + 1
    if nextWind < max(1, int(roundsPerCircle)):
        return nextDealer, nextWind, circleNo, False
    nextCircle = circleNo + 1
    if nextCircle > max(1, int(totalCircles)):
        return nextDealer, 0, circleNo, True
    return nextDealer, 0, nextCircle, False


# 打满一圈后的收尾宽限期：先让全桌看完最终结算，再广播 room_closed 收连接
FINAL_CLOSE_GRACE_SECONDS = 60

# 询问窗口的"防卡死"长兜底：不限时的房间里没人点，也不能永远停在这一张牌上。
# 这不是"出牌限时"，也不下发 claim_deadline（牌桌上不该出现倒计时压力）；
# 只在整窗长时间无人响应时按"过"收窗，让牌局继续（04 §9.3）。
CLAIM_SAFETY_SECONDS = 180


def _asPersistError(error: Exception) -> persist.PersistError:
    """把线程池里冒出来的任意异常统一成 `PersistError`（本来就是则原样返回）。"""
    if isinstance(error, persist.PersistError):
        return error
    return persist.PersistError("DB_WRITE_FAILED", "数据保存失败，请重试", 500)


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
        # 房主收摊后为 True：WS 循环据此结束，避免连接挂在已销毁的演员上
        self.closed = False
        # B-1：本场已经收场（自然打满/房主结束），不再接受开新局；与 closed 分开是因为
        # 「打满」要先让全桌看完最终结算，过一会（或最后一个连接断开）才真正 shutdown。
        self.finalized = False
        # `mj_room.roomStatus='CLOSED'` 是否已确认落库（幂等：只写一次，失败不置位）
        self._closedInDb = False
        # 打满后的兜底回收定时器（60s），由 shutdown 取消
        self._close_task: asyncio.Task | None = None
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
        # 本场抽座结果（每场首局抽一次，整场不重抽，03 §3.4）
        self.seat_draw: dict | None = None
        # 本场第几圈（v1.1.0）：一圈 4 个庄次，一场圈数由 `rule.circles_per_game` 决定
        self.circle_no = 1
        # 本局是否连庄（庄家胡牌后庄位与局风不变）：只用于展示「连庄」角标
        self.dealer_continue = False

        self._gen = 0
        self._turn_task: asyncio.Task | None = None
        self._claim_task: asyncio.Task | None = None
        self._chat_buckets: dict[str, ChatBucket] = defaultdict(ChatBucket)

        # 观战：loginID → 目标绑定；按 loginID 计数，多标签页只占 1 个名额
        self.spectators: dict[str, SpectateBinding] = {}
        self._spectate_tasks: dict[str, asyncio.Task] = {}

        # 非本家庭成员凭码进桌（S10）：先挂起等房主确认，批准前不分配座位、不推送房态。
        # 批准状态按 loginID 记住（同一房间内多标签页/重连不再重复申请）；
        # 拒绝只作用于本次申请——重进会重新提交，房主误点也能改主意。
        self.approved: set[str] = set()
        self.pending: dict[str, dict] = {}

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

    # ---------------------------------------------------------------- 访客待确认（S10）
    def needs_approval(self, login_id: str, is_member: bool) -> bool:
        """非本家庭成员凭码进桌：房主同意前只挂着等，不给座位、不进推送列表。"""
        if is_member or login_id == self.host_login_id:
            return False
        return login_id not in self.approved

    def add_pending(self, login_id: str, display_name: str, color: str, ws: object) -> None:
        item = self.pending.get(login_id)
        if item is None:
            item = {
                "login_id": login_id,
                "display_name": display_name,
                "color": color,
                "requested_at": time.time(),
                "conns": [],
            }
            self.pending[login_id] = item
        if ws not in item["conns"]:
            item["conns"].append(ws)

    def is_pending_conn(self, login_id: str, ws: object) -> bool:
        item = self.pending.get(login_id)
        return bool(item) and ws in item["conns"]

    def pending_requests(self) -> list[dict]:
        """给房主看的申请列表（不含连接对象）。"""
        return [
            {
                "login_id": item["login_id"],
                "display_name": item["display_name"],
                "requested_at": item["requested_at"],
            }
            for item in self.pending.values()
        ]

    def _drop_pending_conn(self, login_id: str, ws: object) -> None:
        item = self.pending.get(login_id)
        if item is None:
            return
        if ws in item["conns"]:
            item["conns"].remove(ws)
        if not item["conns"]:
            self.pending.pop(login_id, None)

    async def _send_pending(self, item: dict, message: dict) -> None:
        """待确认用户不在 `conns` 里，发消息要单独走他们挂起的连接。"""
        for ws in list(item["conns"]):
            try:
                await ws.send_json(message)
            except (RuntimeError, ConnectionError):
                item["conns"].remove(ws)

    async def approve_join(self, operator_login_id: str, login_id: str, allow: bool) -> None:
        """`room.approve`（S10）：房主确认非本家庭访客进桌。

        同意 → 分配座位（满座则观战）、补 welcome + 快照；拒绝 → 通知访客并清掉挂起连接。
        """
        if operator_login_id != self.host_login_id:
            await self.send_error(operator_login_id, "FORBIDDEN", "只有房主可以确认进桌申请")
            return
        item = self.pending.pop(login_id, None)
        if item is None:
            await self.send_error(operator_login_id, "JOIN_NOT_PENDING", "这条进桌申请已经处理过了")
            await self._push_snapshot(operator_login_id)
            return

        if not allow:
            await self._send_pending(
                item,
                make_message(
                    "room.join_denied",
                    {"room_code": self.code, "message": "房主没有同意这次进桌"},
                ),
            )
            await self._push_snapshot(operator_login_id)
            logger.info("拒绝进桌 room=%s login=%s", self.code, login_id)
            return

        self.approved.add(login_id)
        slot = self.assign(login_id, item["display_name"], item["color"])
        if slot is not None:
            await self.drop_spectate(login_id)
        for ws in list(item["conns"]):
            self.attach(login_id, ws)
        chat = await run_in_threadpool(persist.load_messages, self.room_id, 50)
        await self.send(
            login_id, make_message("room.welcome", welcome_payload(self, login_id, slot, chat))
        )
        await self.push_all()
        await self.system_chat(f"房主已同意 {item['display_name']} 进桌")
        logger.info(
            "批准进桌 room=%s login=%s seat=%s",
            self.code,
            login_id,
            slot.seat if slot is not None else "观战",
        )

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
            self.pending.pop(login_id, None)
        else:
            self._drop_conn(login_id, ws)
            # 待确认的访客断开：撤掉申请，房主那张卡片随之消失（推送在调用方做）
            self._drop_pending_conn(login_id, ws)
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
    async def _persist(self, func, *args, required: bool = False):
        """把同步落库丢进线程池。

        默认失败只记日志并返回 None（不阻断对局，01 §7.4）；`required=True` 用于
        收尾类写入（`close_room` / `close_game`）：失败一律转成 `PersistError` 上抛，
        由调用方回 `CLOSE_FAILED` 并保留内存房态，绝不能「内存已关、库里还开」。
        """
        try:
            return await run_in_threadpool(func, *args)
        except Exception as error:  # noqa: BLE001 落库失败不能拖垮牌局
            logger.error(
                "落库失败 room=%s func=%s: %s",
                self.code,
                getattr(func, "__name__", str(func)),
                error,
            )
            if required:
                if isinstance(error, persist.PersistError):
                    raise
                raise _asPersistError(error) from error
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

    async def push_snapshot_to(self, login_id: str) -> None:
        """给单个用户补一版快照（房主收到新的进桌申请时用）。"""
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
                await self._start_game(login_id, data)
            elif msg_type == "game.next":
                await self._next_round(login_id)
            elif msg_type == "game.finish":
                await self._end_game(login_id)
            elif msg_type == "game.action":
                await self._action(login_id, data)
            elif msg_type == "room.pause":
                await self._set_paused(login_id, True, data.get("note"))
            elif msg_type == "room.resume":
                await self._set_paused(login_id, False, data.get("note"))
            elif msg_type == "chat.send":
                await self._chat(login_id, data)
            elif msg_type == "room.approve":
                # S10：房主确认/拒绝非本家庭访客进桌
                await self.approve_join(
                    login_id, str(data.get("login_id") or ""), bool(data.get("allow"))
                )
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

    async def _start_game(self, login_id: str, data: dict | None = None) -> None:
        if self.slot_of_login(login_id) is None:
            await self.send_error(login_id, "NO_SEAT", "你在观战，不能开局")
            return
        if login_id != self.host_login_id:
            await self.send_error(login_id, "NOT_HOST", "只有房主可以开桌")
            return
        if self.finalized:
            # 本场已经收场（打满/房主结束）：这桌不再接受新牌局，回大厅重新开桌
            await self.send_error(login_id, "ROOM_CLOSED", "这桌已经结束了，回大厅再开一桌吧")
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
        if not self._apply_turn_timeout(data):
            await self.send_error(
                login_id, "TIMEOUT_INVALID", "出牌限时只能设 10-120 秒，0 表示不限时"
            )
            return
        await self._begin_game()

    def _apply_turn_timeout(self, data: dict | None) -> bool:
        """开局前由房主定本场出牌限时（03 §4.1 的开关纪律：关闭时只留 enabled）。

        `enabled=false`（默认）即不限时，`seconds` 归 0；开启时只接受 10-120 秒。
        只改内存里的本场规则，不动房间/模板快照——下一场重新选。
        """
        payload = (data or {}).get("turn_timeout")
        if not isinstance(payload, dict):
            return True
        timeout = getattr(self.rule, "turn_timeout", None)
        if timeout is None:
            # 该族没有「出牌限时」概念，忽略这项设置
            return True
        enabled = bool(payload.get("enabled"))
        try:
            seconds = int(payload.get("seconds") or 0)
        except (TypeError, ValueError):
            return False
        if not enabled:
            timeout.enabled = False
            timeout.seconds = 0
            self._sync_timeout_snapshot()
            return True
        if not 10 <= seconds <= 120:
            return False
        timeout.enabled = True
        timeout.seconds = seconds
        self._sync_timeout_snapshot()
        return True

    def _sync_timeout_snapshot(self) -> None:
        """把本场限时写回内存快照，场次落库（mj_game.ruleSnapshot）与牌桌摘要保持一致。"""
        snapshot = self.rule_snapshot if isinstance(self.rule_snapshot, dict) else None
        if snapshot is None:
            return
        timeout = getattr(self.rule, "turn_timeout", None)
        config = snapshot.get("config")
        if isinstance(config, dict) and timeout is not None:
            config["turn_timeout"] = {
                "enabled": bool(timeout.enabled),
                "seconds": int(timeout.seconds or 0),
            }

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
        self.circle_no = 1
        self.dealer_continue = False
        self.engine = registry.create_engine(
            self.rule_family_code or "generic",
            self.rule,
            seats,
            round_no=1,
            circle_no=self.circle_no,
        )
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

    def _next_dealer_state(self) -> tuple[int, int, int, bool]:
        """结算后下一局的 `(庄家座位, 局风, 圈序, 本场是否结束)`。

        庄家是否连庄由族的 `next_dealer(result)` 决定：返回庄家自己 → 庄位与局风都不动，
        局号照常 +1（前端据此显示「连庄」）；返回下家 → 庄家换人、局风 +1。
        局风攒满一圈的 4 个庄次（北位下庄）即本圈结束：
          - 还没打满 `rule.circles_per_game` 圈 → 圈序 +1、局风回到东风；
          - 已经打满 → 本场收场。
        座位整场只抽一次，换圈不重抽，庄家照座位顺延（北位之后回到东位）。
        未结算（`engine.result is None`，如无杠重发）时按换庄算，仅用于兜底。
        """
        engine = self.engine
        if engine is None:
            return 0, 0, self.circle_no, True
        dealerSeat = int(engine.dealer_seat)
        roundWind = int(engine.round_wind)
        try:
            nextDealer = int(engine.next_dealer(engine.result))
        except Exception:  # 族实现异常不该把牌桌卡住：退回「下家坐庄」
            logger.exception("next_dealer 失败 room=%s，按换庄处理", self.code)
            nextDealer = (dealerSeat + 1) % 4
        return nextRoundState(
            dealerSeat,
            roundWind,
            self.circle_no,
            nextDealer,
            roundsPerCircle=int(getattr(self.rule, "rounds_per_game", ROUNDS_PER_CIRCLE) or ROUNDS_PER_CIRCLE),
            totalCircles=int(getattr(self.rule, "circles_per_game", CIRCLES_PER_GAME) or CIRCLES_PER_GAME),
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
        if self.finalized:
            # 已收场：不再推进新局（重试关房的入口是 game.finish，不是 game.next）
            await self.send_error(login_id, "ROOM_CLOSED", "这桌已经结束了，回大厅再开一桌吧")
            return
        # 圈结束只看庄次：第 4 个庄次（北位）下庄即本圈结束；打满 `circles_per_game` 圈才收场
        dealerSeat, roundWind, circleNo, finished = self._next_dealer_state()
        if finished:
            try:
                await self._finish_game()
            except persist.PersistError:
                # 收尾落库失败：房态停在 finished，房主可重试（再点"下一局"或"关闭牌桌"）
                await self.send_error(login_id, "CLOSE_FAILED", "关房失败，请在大厅重试")
            return
        for slot in self.slots:
            if slot is not None:
                slot.ready = True
        # 局号照常 +1（历史一局一条记录），庄家与局风由结算决定：连庄保持、下庄顺延。
        # 无杠重发在同一局内由引擎自行处理（不发 game.next），因此这里只推进局号。
        roundNo = self.engine.round_no + 1
        self.dealer_continue = dealerSeat == int(self.engine.dealer_seat)
        self.circle_no = circleNo
        self.engine = registry.create_engine(
            self.rule_family_code or "generic",
            self.rule,
            list(self.engine.seats.values()),
            round_no=roundNo,
            dealer_seat=dealerSeat,
            round_wind=roundWind,
            circle_no=circleNo,
        )
        self.last_result = None
        await self._after(self.engine.start_round())

    async def _finish_game(self) -> None:
        """打满所选圈数（一场结束）：收尾路径之一（另一条是 `_end_game` 的提前收场）。

        B-1 定稿（唯一口径，不保留"立即 shutdown"的第二种写法）：
          1. 场次落库 FINISHED；
          2. 广播 `event.game_finished{final:true}`，让全桌先看完最终总分；
          3. 立刻落库 `mj_room.roomStatus='CLOSED'` —— 大厅马上就看不到这桌；
          4. **不**立刻广播 `event.room_closed`：标记 `finalized`，交给"最后一个连接断开"
             （`main/ws.py` 的 finally）或 60s 兜底定时器执行 `shutdown`。

        落库失败直接抛 `PersistError`：房态停在 `finished`、库里仍 OPEN，房主可以再点
        一次"关闭牌桌"重试，绝不会出现"内存关了、库里还开"的幽灵房。
        """
        if self.finalized:
            return
        if self.game_id is not None:
            await self._persist(persist.close_game, self.game_id, required=True)
            self.game_id = None
        self.status = "finished"
        scores = [
            {"seat": slot.seat, "name": slot.display_name, "total": 0}
            for slot in self.slots
            if slot is not None
        ]
        if self.engine is not None:
            for entry in scores:
                entry["total"] = self.engine.seats[entry["seat"]].total_score
        await self.broadcast(
            make_message("event.game_finished", {"scores": scores, "final": True})
        )
        await self.push_all()
        await self._persist_closed(self.host_login_id)
        self.finalized = True
        self._schedule_close()

    async def _end_game(self, login_id: str) -> None:
        """`game.finish`：开桌的人可以结束本场（不必等打满 `circles_per_game` 圈）。幂等。

        家庭局的现实：有人要走、时间不够时，房主一句话就能收摊，而不是拖着继续打。
        已打完的局与积分全部保留，只有正在进行的这一局作废。四种状态各自的口径：
          - `playing`：正常收场（场次 ABORTED）→ 落库 CLOSED → shutdown；
          - `finished`：自然打满后再点一次 "关闭牌桌" —— 幂等收摊成功，不报错；
          - `closed` / 已 finalized：重复点击幂等成功（只补一次 shutdown）；
          - `waiting`：没有牌局可结束，提示回大厅关桌。
        """
        slot = self.slot_of_login(login_id)
        if slot is None:
            await self.send_error(login_id, "NO_SEAT", "你在观战，不能结束牌局")
            return
        if login_id != self.host_login_id:
            await self.send_error(login_id, "NOT_HOST", "只有开桌的人可以结束牌局")
            return
        if self.finalized or self.status in ("finished", "closed"):
            # 已经收场：幂等成功（重复点击、3s 超时兜底都会走到这里）
            try:
                await self._close_room(login_id)
            except persist.PersistError:
                await self.send_error(login_id, "CLOSE_FAILED", "关房失败，请在大厅重试")
            return
        if self.engine is None or self.status != "playing":
            await self.send_error(
                login_id, "NOT_PLAYING", "牌局还没开始，回大厅关闭牌桌即可"
            )
            return
        # 先标记收场：万一落库失败，重试也不会被上面的状态守卫挡住（幂等可重试）
        self.finalized = True
        await self.system_chat(f"{slot.display_name} 结束了本场牌局")
        await self._abort_game(slot)
        try:
            await self._close_room(login_id)
        except persist.PersistError:
            # 内存已收场、库里仍 OPEN：给房主一条明确的失败提示（前端不跳转，可重试）
            await self.send_error(login_id, "CLOSE_FAILED", "关房失败，请在大厅重试")

    # ---------------------------------------------------------------- 关房（唯一出口）
    async def _persist_closed(self, operator_login_id: str) -> None:
        """把 `mj_room` 置 CLOSED（幂等）：写成功过就不再写，失败上抛 PersistError。"""
        if self._closedInDb:
            return
        await self._persist(
            persist.close_room, self.room_id, operator_login_id, required=True
        )
        self._closedInDb = True

    async def _close_room(self, operator_login_id: str = "") -> None:
        """唯一收尾出口：落库 CLOSED → `status="closed"` → `shutdown`（幂等）。

        `persist.close_room` 失败直接抛 `PersistError`，此时**不动内存房态**：
        调用方回 `error{CLOSE_FAILED}`，房主可原地重试，或回大厅关桌。
        """
        await self._persist_closed(operator_login_id)
        self.finalized = True
        self.status = "closed"
        await self.shutdown(operator_login_id)

    def _schedule_close(self, delay: float = FINAL_CLOSE_GRACE_SECONDS) -> None:
        """打满后的兜底回收：最后一个人不肯断线，也要在 `delay` 秒后把演员收掉。"""
        if self.closed:
            return
        task = self._close_task
        if task is not None and not task.done():
            return
        self._close_task = asyncio.create_task(self._close_after(delay))

    def should_reap(self) -> bool:
        """打满收场后「库里已 CLOSED 且一个连接都不剩」：可以立刻把演员收掉。

        落库没成功（`_closedInDb=False`）时**不**回收：留着内存房态，房主还能重试关房，
        避免出现"内存没了、库里还 OPEN"的第二种幽灵房。
        """
        return bool(self._closedInDb and not self.conns and not self.closed)

    async def _close_after(self, delay: float) -> None:
        await asyncio.sleep(max(0.0, delay))
        self._close_task = None
        if self.closed:
            return
        async with self.lock:
            if self.closed:
                return
            await self.shutdown(self.host_login_id)

    async def shutdown(self, operator_login_id: str = "") -> None:
        """关房收摊：广播 `event.room_closed` → 释放观战 → 从注册表移除演员。

        `mj_room.roomStatus` 由调用方落库（`_close_room` 与 HTTP 关房各一次），
        这里只管内存房态与连接：牌桌上的人收到事件后断开，不再重连。幂等。
        """
        from realtime.manager import room_manager  # 局部导入：manager 反过来依赖本模块

        if self.closed:
            return
        self.closed = True
        self.finalized = True
        self._clear_timers()
        task = self._close_task
        self._close_task = None
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self.turn_deadline = None
        self.claim_deadline = None
        # 大厅直接关房时牌局可能还在进行：场次标中断，别留一条永远「进行中」的僵尸记录
        if self.game_id is not None:
            settled = self.engine is not None and self.engine.phase == "settled"
            await self._persist(
                persist.close_game if settled else persist.abort_game, self.game_id
            )
            self.game_id = None
        await self.close_spectate()
        # 待确认的访客还没进桌：告知房间已关，别让他们挂在「等房主确认」的遮罩上
        for item in list(self.pending.values()):
            await self._send_pending(
                item,
                make_message(
                    "room.join_denied",
                    {"room_code": self.code, "message": "房间已经关了"},
                ),
            )
        self.pending.clear()
        await self.broadcast(
            make_message("event.room_closed", {"room_code": self.code, "by": operator_login_id})
        )
        room_manager.remove(self.code)
        logger.info("关房 room=%s by=%s", self.code, operator_login_id or "system")

    async def _abort_game(self, slot: PlayerSlot) -> None:
        """提前收场：落库 ABORTED → 广播整场结算 → 房态清空。

        清掉半局的 engine 而不是留成 `finished`：`finished` 会让重新进桌的家人
        看到一副打了一半又没人能动的牌。随后由 `_close_room` 关房销毁演员。
        """
        self._clear_timers()
        self.turn_deadline = None
        self.claim_deadline = None
        engine = self.engine
        scores = []
        for item in self.slots:
            if item is None:
                continue
            total = 0
            if engine is not None and item.seat in engine.seats:
                total = engine.seats[item.seat].total_score
            scores.append({"seat": item.seat, "name": item.display_name, "total": total})
        # 本局已结算（比如打满局的最后一局刚结算完）时没有「作废的局」，
        # 场次记 FINISHED；只有中途收场才是 ABORTED（与进程重启的中断口径一致）。
        settled = engine is not None and engine.phase == "settled"
        if self.game_id is not None:
            await self._persist(
                persist.close_game if settled else persist.abort_game, self.game_id
            )
        logger.info("提前收场 room=%s game=%s by=%s", self.code, self.game_id, slot.login_id)

        self.status = "waiting"
        self.engine = None
        self.game_id = None
        self.last_result = None
        self.seat_draw = None
        self.paused = False
        self.paused_by_seat = None
        self.paused_by_login_id = None
        self.paused_note = None
        for item in self.slots:
            if item is not None:
                item.ready = False
        await self.broadcast(
            make_message(
                "event.game_finished",
                {
                    "scores": scores,
                    "aborted": True,
                    "ended_by_seat": slot.seat,
                    "ended_by_name": slot.display_name,
                },
            )
        )
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
        # 即使没有事件也要推快照：过胡（pass 在胡阶段）不产生事件、也不关闭窗口，
        # 但该玩家必须立刻看到补发的碰/杠/吃选项（04 §9.5 两段式）。
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
            # 本场结束看庄次与圈序（连庄会让局号超过每圈 4 局，不能拿局号比）
            "is_last_round": self._next_dealer_state()[3],
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
            # 终局四家手牌与副露：结算页直接回放赢家 14 张，不必等战绩落库后回查
            "final_hands": list(settled.final_hands),
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
        # 连庄要说清楚，否则下一局还是同一位庄家会让人以为没挪庄是 bug
        if not settled.is_draw and self._next_dealer_state()[0] == engine.dealer_seat:
            text += " · 庄家连庄"
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
            limit = self._claim_window_seconds()
            self.turn_deadline = None
            if limit:
                self.claim_deadline = now + limit
                self._claim_task = asyncio.create_task(self._claim_timeout(gen, limit))
            else:
                # 不限时：牌桌不显示倒计时（claim_deadline 保持 None），
                # 但挂一条防卡死长兜底，避免所有人都不点就永远停在这张牌上（04 §9.3）
                self.claim_deadline = None
                self._claim_task = asyncio.create_task(
                    self._claim_timeout(gen, CLAIM_SAFETY_SECONDS, safety=True)
                )
        elif engine.phase == "discard" and getattr(self.rule.turn_timeout, "enabled", False):
            seconds = self.rule.turn_timeout.seconds
            self.turn_deadline = now + seconds
            self.claim_deadline = None
            self._turn_task = asyncio.create_task(self._turn_timeout(gen, seconds))
        else:
            self.turn_deadline = None
            self.claim_deadline = None

    def _claim_window_seconds(self) -> int:
        """吃/碰/杠/胡 的响应窗口秒数；0 = 不给倒计时（跟「出牌限时」同一个总开关）。

        默认不限时：家庭局里漏看一眼提示就被自动「过」掉，比慢一点难受得多。
        房主开局选了限时，响应仍按规则里的 `claim_window_seconds`（3-30 秒）询问。
        返回 0 时仍会挂一条 `CLAIM_SAFETY_SECONDS` 的防卡死兜底（不下发 deadline）。
        """
        if not getattr(getattr(self.rule, "turn_timeout", None), "enabled", False):
            return 0
        return int(getattr(self.rule, "claim_window_seconds", 0) or 0)

    def _clear_timers(self) -> None:
        for task in (self._turn_task, self._claim_task):
            if task is not None and not task.done():
                task.cancel()
        self._turn_task = None
        self._claim_task = None

    async def _claim_timeout(self, gen: int, seconds: float, safety: bool = False) -> None:
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
            # 限时窗口说"超时"；不限时的长兜底说"长时间无人响应"，别让家人以为被限时催了
            text = "长时间无人响应，本张牌按过处理" if safety else "超时未响应，按过处理"
            await self.broadcast(make_message("event.claim_timeout", {"message": text}))
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
