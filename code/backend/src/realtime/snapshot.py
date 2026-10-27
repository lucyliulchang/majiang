"""逐连接生成快照：手牌只对本人或观战目标明文，其他人只给张数与副露。

从协议层杜绝「抓包看别人牌」：观战者同一时刻只跟随 1 名在座玩家（S5b），
未选目标时只收公共状态（hand=[]、drawn=null、legal.actions=[]）。
"""

from game.tiles import tiles_from_counts


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
        "room": {
            # 04 §9.5 字段
            "room_code": actor.code,
            "room_name": actor.name,
            "host_login_id": actor.host_login_id,
            "family_code": actor.family_code,
            "family_name": actor.family_name,
            "rule_name": actor.rule_name,
            "rule_family_code": actor.rule_family_code,
            "rule_brief": rule.brief(),
            "spectator_count": actor.spectator_count(),
            "spectate_seat_viewer_counts": spectator_counts,
            # 兼容旧前端的别名（S6 前端切到上名字段后删除）
            "code": actor.code,
            "name": actor.name,
        },
        "self_seat": viewer_seat,
        "spectate": spectate,
        "seats": [_seat_view(actor, seat, look_seat, spectator_counts) for seat in range(4)],
        "status": actor.status,
        "round_no": engine.round_no if engine else 0,
        "dealer_seat": engine.dealer_seat if engine else None,
        # 局风 = 局序 - 1：第 1 局东、第 2 局南…（03 §3.4，与谁是庄家无关）
        "round_wind": engine.round_wind if engine else 0,
        # 生效选项：开关关闭时只有 enabled，不下发从属值（03 §10）
        "rule_options": engine.snapshot_options() if engine else {},
        "game_total_rounds": rule.rounds_per_game,
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
            if rule.ting_hint.enabled and engine.phase == "discard" and engine.turn == look_seat:
                tenpai = engine.tenpai_map(look_seat)
                payload["tenpai"] = {str(tile): waits for tile, waits in tenpai.items()}

    if engine.phase == "discard" and rule.turn_timeout.enabled:
        payload["deadline"] = actor.turn_deadline
    if engine.phase == "claim":
        payload["claim_deadline"] = actor.claim_deadline
    return payload
