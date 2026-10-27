from game.hand import HandContext
from game.patterns import collect_wins, is_winning, winning_tiles
from game.tiles import counts_from_tiles
from game.families.generic.config import RuleConfig

RULE = RuleConfig()


def ctx_of(hand, win_tile=None, self_draw=True, melds=None):
    tiles = hand if isinstance(hand, list) else hand
    return HandContext(
        counts=counts_from_tiles(tiles),
        melds=melds or [],
        win_tile=win_tile,
        is_self_draw=self_draw,
    )


def test_plain_win(hand):
    assert is_winning(ctx_of(hand("123m456m789m123p11s"), 18), RULE)


def test_missing_one_tile_is_not_win(hand):
    assert not is_winning(ctx_of(hand("123m456m789m123p12s"), 19), RULE)


def test_all_pongs_is_peng_peng_hu(hand):
    tiles = hand("111m333m555p777s11z")
    wins = collect_wins(ctx_of(tiles, 27), RULE)
    ids = [hit.id for win in wins for hit in win.fan_hits]
    assert "peng_peng_hu" in ids


def test_pure_suit_beats_mixed(hand):
    tiles = hand("123m456m789m234m55m")
    wins = collect_wins(ctx_of(tiles, 4), RULE)
    ids = [hit.id for win in wins for hit in win.fan_hits]
    assert "qing_yi_se" in ids
    assert "hun_yi_se" not in ids


def test_multiple_decompositions_picks_highest(hand):
    """112233m 456p 789s 99s 可以拆成顺子也可以拆成刻子结构，取番值高的。"""
    tiles = hand("111m222m333m456p99s")
    wins = collect_wins(ctx_of(tiles, 17), RULE)
    assert any(win.pattern_id == "standard" for win in wins)


def test_tenpai_detection(hand):
    tiles = hand("123m456m789m123p1s")
    waits = winning_tiles(HandContext(counts=counts_from_tiles(tiles)), RULE)
    assert 18 in waits
    assert 19 not in waits


def test_tenpai_multi_wait(hand):
    """边张与嵌张同时听：123m 456m 789m 12p 55s 听 3p。"""
    tiles = hand("123m456m789m12p55s")
    waits = winning_tiles(HandContext(counts=counts_from_tiles(tiles)), RULE)
    assert 11 in waits


def test_win_with_meld(hand):
    from game.hand import Meld

    melds = [Meld(kind="pong", tiles=[0, 0, 0], from_seat=1)]
    tiles = hand("456m789m123p11s")
    assert is_winning(ctx_of(tiles, 18, melds=melds), RULE)


def test_open_hand_is_not_men_qian(hand):
    from game.hand import Meld

    melds = [Meld(kind="pong", tiles=[0, 0, 0], from_seat=1)]
    tiles = hand("456m789m123p11s")
    wins = collect_wins(ctx_of(tiles, 18, melds=melds), RULE)
    ids = [hit.id for win in wins for hit in win.fan_hits]
    assert "men_qian" not in ids
