"""快照 `seats[].is_out`：血战已胡退出的座位才为 true，其它族恒为 false。

前端据此才显示「已胡」角标，因此这里锁住口径：柏氏/广东等没有 `out_seats` 的引擎
必须一律 false，不能因为字段缺省而在界面冒出一个「已胡」。
"""

from types import SimpleNamespace

from game.hand import Meld
from realtime.snapshot import _seat_view


def _slot(seat: int) -> SimpleNamespace:
    return SimpleNamespace(
        seat=seat,
        login_id=f"1380000000{seat}",
        display_name=f"玩家{seat}",
        color="#C9A063",
        ready=True,
        connected=True,
    )


def _actor(engine) -> SimpleNamespace:
    return SimpleNamespace(
        engine=engine,
        slots=[_slot(seat) for seat in range(4)],
        host_login_id="13800000000",
    )


def _engine(out_seats=None):
    state = SimpleNamespace(counts=[0] * 34, melds=[], round_score=0, total_score=0)
    kwargs = {
        "seats": {seat: state for seat in range(4)},
        "dealer_seat": 0,
        "seat_wind": lambda seat: seat % 4,
    }
    if out_seats is not None:
        kwargs["out_seats"] = out_seats
    return SimpleNamespace(**kwargs)


def test_seat_view_marks_out_seat_for_sichuan():
    actor = _actor(_engine(out_seats={1, 2}))
    counts = [0, 0, 0, 0]
    assert _seat_view(actor, 1, None, counts)["is_out"] is True
    assert _seat_view(actor, 2, None, counts)["is_out"] is True
    assert _seat_view(actor, 0, None, counts)["is_out"] is False
    assert _seat_view(actor, 3, None, counts)["is_out"] is False


def test_seat_view_out_false_when_family_has_no_out_seats():
    # 柏氏 / 广东 / 通用族：引擎没有 out_seats 属性
    actor = _actor(_engine())
    counts = [0, 0, 0, 0]
    assert all(_seat_view(actor, seat, None, counts)["is_out"] is False for seat in range(4))


def test_seat_view_out_false_before_game_starts():
    actor = _actor(None)
    counts = [0, 0, 0, 0]
    assert all(_seat_view(actor, seat, None, counts)["is_out"] is False for seat in range(4))


def test_hidden_kong_tiles_only_visible_to_owner():
    """暗杠的牌面只对本人（或观战目标）下发：其他连接只拿到 4 张空 tiles。"""
    engine = _engine()
    engine.seats[1] = SimpleNamespace(
        counts=[0] * 34,
        melds=[
            Meld(kind="kong_hidden", tiles=[26] * 4),
            Meld(kind="kong_exposed", tiles=[4] * 4, from_seat=0, claim_tile=4),
        ],
        round_score=0,
        total_score=0,
    )
    actor = _actor(engine)
    counts = [0, 0, 0, 0]

    others = _seat_view(actor, 1, None, counts)["melds"]
    assert others[0]["kind_name"] == "暗杠" and others[0]["count"] == 4
    assert others[0]["tiles"] == [], "暗杠牌面不能下发给其他玩家"
    assert others[0]["claim_tile"] is None
    # 明杠是桌上公开的牌，照旧下发
    assert others[1]["tiles"] == [4, 4, 4, 4]

    mine = _seat_view(actor, 1, 1, counts)["melds"]
    assert mine[0]["tiles"] == [26, 26, 26, 26], "本人要看到自己暗杠的牌"
