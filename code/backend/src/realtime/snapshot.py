"""逐座位生成快照：只把自己的手牌明文下发，其他人只给张数与副露。

从协议层杜绝"抓包看别人牌"。
"""

from game.tiles import tiles_from_counts


def _seat_view(actor, seat: int, viewer_seat: int | None) -> dict | None:
    slot = actor.slots[seat]
    if slot is None:
        return None
    engine = actor.engine
    hand_count = 0
    melds: list[dict] = []
    round_score = 0
    total_score = 0
    if engine is not None:
        state = engine.seats.get(seat)
        if state is not None:
            hand_count = sum(state.counts)
            reveal = viewer_seat == seat
            melds = [meld.to_dict(reveal=reveal or meld.kind != "kong_hidden") for meld in state.melds]
            round_score = state.round_score
            total_score = state.total_score
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
    }


def build_snapshot(actor, viewer_seat: int | None) -> dict:
    engine = actor.engine
    rule = actor.rule
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
            # 兼容旧前端的别名（S6 前端切到上名字段后删除）
            "code": actor.code,
            "name": actor.name,
        },
        "self_seat": viewer_seat,
        "seats": [_seat_view(actor, seat, viewer_seat) for seat in range(4)],
        "status": actor.status,
        "round_no": engine.round_no if engine else 0,
        "dealer_seat": engine.dealer_seat if engine else None,
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

    if viewer_seat is not None:
        state = engine.seats.get(viewer_seat)
        if state is not None:
            hands = tiles_from_counts(state.counts)
            payload["hand"] = hands
            if engine.turn == viewer_seat and engine.last_draw is not None:
                payload["drawn"] = engine.last_draw
            payload["legal"] = engine.legal_actions(viewer_seat)
            if rule.ting_hint.enabled and engine.phase == "discard" and engine.turn == viewer_seat:
                tenpai = engine.tenpai_map(viewer_seat)
                payload["tenpai"] = {str(tile): waits for tile, waits in tenpai.items()}

    if engine.phase == "discard" and rule.turn_timeout.enabled:
        payload["deadline"] = actor.turn_deadline
    if engine.phase == "claim":
        payload["claim_deadline"] = actor.claim_deadline
    return payload
