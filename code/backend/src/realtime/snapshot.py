"""逐连接生成快照：手牌只对本人或观战目标明文，其他人只给张数与副露。

从协议层杜绝「抓包看别人牌」：观战者同一时刻只跟随 1 名在座玩家（S5b），
未选目标时只收公共状态（hand=[]、drawn=null、legal.actions=[]）。
"""

from game.families.generic.config import CIRCLES_PER_GAME
from game.tiles import tiles_from_counts


def _room_view(actor) -> dict:
    """`room` 段（欢迎包与快照共用，04 §9.5 字段）。"""
    return {
        # 房间主键：前端 3s 超时兜底要直接调 `POST /api/rooms/{id}/close`（B-1）
        "room_id": actor.room_id,
        "room_code": actor.code,
        "room_name": actor.name,
        "host_login_id": actor.host_login_id,
        "family_code": actor.family_code,
        "family_name": actor.family_name,
        "rule_name": actor.rule_name,
        "rule_family_code": actor.rule_family_code,
        "rule_brief": actor.rule.brief(),
        "spectator_count": actor.spectator_count(),
        "spectate_seat_viewer_counts": actor.spectator_counts(),
        # 兼容旧前端的别名（S6 前端切到上名字段后删除）
        "code": actor.code,
        "name": actor.name,
    }


def welcome_payload(actor, login_id: str, slot, chat: list[dict]) -> dict:
    """`room.welcome`（04 §9.1）：首次握手与房主批准访客进桌时共用同一份结构。"""
    return {
        "room": _room_view(actor),
        "self_seat": slot.seat if slot is not None else None,
        "spectate": actor.spectate_of(login_id),
        "chat": chat,
    }


def _seat_view(actor, seat: int, look_seat: int | None, spectator_counts: list[int]) -> dict | None:
    slot = actor.slots[seat]
    if slot is None:
        return None
    engine = actor.engine
    hand_count = 0
    melds: list[dict] = []
    round_score = 0
    total_score = 0
    wind = None
    if engine is not None:
        state = engine.seats.get(seat)
        if state is not None:
            hand_count = sum(state.counts)
            reveal = look_seat == seat
            melds = [meld.to_dict(reveal=reveal or meld.kind != "kong_hidden") for meld in state.melds]
            round_score = state.round_score
            total_score = state.total_score
        # 门风：(seat - 庄家座位) % 4，庄家恒为东（03 §3.4）
        wind = engine.seat_wind(seat)
    return {
        "seat": seat,
        "login_id": slot.login_id,
        "display_name": slot.display_name,
        "color": slot.color,
        "ready": slot.ready,
        "connected": slot.connected,
        "is_host": slot.login_id == actor.host_login_id,
        "hand_count": hand_count,
        "melds": melds,
        "round_score": round_score,
        "total_score": total_score,
        # 该座位当前围观人数（0–10），全房可见、不含观战者身份
        "spectator_count": spectator_counts[seat],
        # S6 追加：门风与庄家标记（04 §9.5；抽座结果只广播一次，重连靠这里恢复）
        "wind": wind,
        "is_dealer": bool(engine is not None and seat == engine.dealer_seat),
    }


def build_snapshot(actor, viewer_seat: int | None, viewer_login_id: str = "") -> dict:
    """`viewer_seat=None` 表示观战连接：手牌取 `spectate.target_seat` 的明文。"""
    engine = actor.engine
    rule = actor.rule
    spectator_counts = actor.spectator_counts()
    spectate = None if viewer_seat is not None else actor.spectate_of(viewer_login_id)
    spectate_seat = spectate["target_seat"] if spectate else None
    look_seat = viewer_seat if viewer_seat is not None else spectate_seat

    payload = {
        "room": _room_view(actor),
        "self_seat": viewer_seat,
        "spectate": spectate,
        # 房主专属：非本家庭成员凭码申请进桌，等房主在牌桌上确认（S10）
        "join_requests": (
            actor.pending_requests() if viewer_login_id == actor.host_login_id else []
        ),
        "seats": [_seat_view(actor, seat, look_seat, spectator_counts) for seat in range(4)],
        "status": actor.status,
        "round_no": engine.round_no if engine else 0,
        "dealer_seat": engine.dealer_seat if engine else None,
        # 局风 = 庄次（0 东 → 3 北）：每换一次庄 +1，庄家胡牌连庄时保持不变，
        # 因此连庄局里 round_wind 不一定等于 round_no - 1（03 §3.4）
        "round_wind": engine.round_wind if engine else 0,
        # 圈序（v1.1.0）：一圈 4 个庄次，一场圈数由规则 `circles_per_game` 决定；
        # `round_in_circle` 是本圈第几局（1–4，连庄时停在同一值不出来）
        "circle_no": engine.circle_no if engine else int(getattr(actor, "circle_no", 1) or 1),
        "total_circles": max(1, int(getattr(rule, "circles_per_game", CIRCLES_PER_GAME) or CIRCLES_PER_GAME)),
        "rounds_per_circle": max(1, int(getattr(rule, "rounds_per_game", 4) or 4)),
        "round_in_circle": (engine.round_wind + 1) if engine else 0,
        "dealer_continue": bool(getattr(actor, "dealer_continue", False)),
        # 生效选项：开关关闭时只有 enabled，不下发从属值（03 §10）
        "rule_options": engine.snapshot_options() if engine else {},
        # 暂停（04 §9.4）：房态字段，柏氏等支持 pause 的族才可能为 true
        "paused": {
            "paused": bool(getattr(actor, "paused", False)),
            "by_seat": getattr(actor, "paused_by_seat", None),
            "note": getattr(actor, "paused_note", None),
        },
        # 计划总局数 = 每圈局数 × 圈数（连庄会让实际局数更多，展示用本圈进度即可）
        "game_total_rounds": max(1, int(getattr(rule, "rounds_per_game", 4) or 4))
        * max(1, int(getattr(rule, "circles_per_game", CIRCLES_PER_GAME) or CIRCLES_PER_GAME)),
        "hand": [],
        "drawn": None,
        "turn": None,
        "phase": "waiting",
        "wall_count": 0,
        "discards": [[], [], [], []],
        "last_discard": None,
        "legal": {"actions": []},
        "tenpai": {},
        "deadline": None,
        "result": actor.last_result,
        "claim_deadline": None,
    }
    if engine is None:
        return payload

    payload["turn"] = engine.turn
    payload["phase"] = engine.phase
    payload["wall_count"] = engine.remaining
    payload["discards"] = [list(engine.seats[seat].discards) for seat in range(4)]
    if engine.last_discard is not None:
        payload["last_discard"] = {
            "seat": engine.last_discard_seat,
            "tile": engine.last_discard,
        }

    # 手牌只给本人或观战目标；观战者 legal 恒为空（不能操作牌局）
    if look_seat is not None:
        state = engine.seats.get(look_seat)
        if state is not None:
            payload["hand"] = tiles_from_counts(state.counts)
            if engine.turn == look_seat and engine.last_draw is not None:
                payload["drawn"] = engine.last_draw
            if viewer_seat is not None:
                payload["legal"] = engine.legal_actions(viewer_seat)
            # ting_hint 不是每族都有（柏氏没有听牌提示，03 §7）
            if (
                getattr(getattr(rule, "ting_hint", None), "enabled", False)
                and engine.phase == "discard"
                and engine.turn == look_seat
            ):
                tenpai = engine.tenpai_map(look_seat)
                payload["tenpai"] = {str(tile): waits for tile, waits in tenpai.items()}

    if engine.phase == "discard" and getattr(rule.turn_timeout, "enabled", False):
        payload["deadline"] = actor.turn_deadline
    # 响应窗口：默认不限时（`claim_deadline=None`），只有开了限时才下发倒计时
    if engine.phase == "claim" and actor.claim_deadline is not None:
        payload["claim_deadline"] = actor.claim_deadline
    return payload
