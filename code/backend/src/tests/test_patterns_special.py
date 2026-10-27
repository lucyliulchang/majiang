from app.game.hand import HandContext
from app.game.patterns import collect_wins, is_winning
from app.game.tiles import counts_from_tiles
from app.schemas.rule import PatternSwitches, RuleConfig, ThirteenUnrelatedOptions

ORPHANS = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]


def ctx(tiles):
    return HandContext(counts=counts_from_tiles(tiles), win_tile=tiles[-1], is_self_draw=True)


def fan_ids(tiles, rule):
    return {hit.id for win in collect_wins(ctx(tiles), rule) for hit in win.fan_hits}


def test_seven_pairs(hand):
    tiles = hand("11m22m33m44m55m66m77m")
    rule = RuleConfig()
    assert is_winning(ctx(tiles), rule)
    assert "qi_dui" in fan_ids(tiles, rule)


def test_long_seven_pairs(hand):
    tiles = hand("1111m22m33m44m55m66m")
    rule = RuleConfig()
    assert "long_qi_dui" in fan_ids(tiles, rule)


def test_seven_pairs_needs_all_pairs(hand):
    tiles = hand("11m22m33m44m55m67m79m")
    assert not is_winning(ctx(tiles), RuleConfig())


def test_seven_pairs_disabled(hand):
    rule = RuleConfig(patterns=PatternSwitches(seven_pairs=False))
    tiles = hand("11m22m33m44m55m66m77m")
    # 这副牌同时也能拆成标准胡，所以只断言七对牌型不再命中
    ids = {win.pattern_id for win in collect_wins(ctx(tiles), rule)}
    assert "seven_pairs" not in ids
    assert fan_ids(tiles, rule).isdisjoint({"qi_dui", "long_qi_dui"})


def test_thirteen_orphans():
    tiles = ORPHANS + [27]
    rule = RuleConfig()
    assert is_winning(ctx(tiles), rule)
    assert "shi_san_yao" in fan_ids(tiles, rule)


def test_thirteen_orphans_needs_all_kinds():
    tiles = ORPHANS[:-1] + [0, 27]
    assert not is_winning(ctx(tiles), RuleConfig())


def test_thirteen_unrelated_basic(hand):
    rule = RuleConfig(
        patterns=PatternSwitches(
            thirteen_unrelated=ThirteenUnrelatedOptions(enabled=True, min_gap=3)
        )
    )
    tiles = hand("147m147p1s1234567z")
    assert is_winning(ctx(tiles), rule)
    assert "shi_san_bu_kao" in fan_ids(tiles, rule)


def test_thirteen_unrelated_gap_violation(hand):
    rule = RuleConfig(
        patterns=PatternSwitches(
            thirteen_unrelated=ThirteenUnrelatedOptions(enabled=True, min_gap=3)
        )
    )
    tiles = hand("123m147p1s1234567z")
    assert not is_winning(ctx(tiles), rule)


def test_thirteen_unrelated_loose_gap_passes(hand):
    rule = RuleConfig(
        patterns=PatternSwitches(
            thirteen_unrelated=ThirteenUnrelatedOptions(enabled=True, min_gap=2)
        )
    )
    tiles = hand("135m147p1s1234567z")
    assert is_winning(ctx(tiles), rule)


def test_thirteen_unrelated_requires_all_honors(hand):
    rule = RuleConfig(
        patterns=PatternSwitches(
            thirteen_unrelated=ThirteenUnrelatedOptions(
                enabled=True, require_all_honors=True, min_gap=3
            )
        )
    )
    full = hand("147m147p1s1234567z")
    assert is_winning(ctx(full), rule)
    fewer_honors = hand("147m147p147s")
    assert not is_winning(ctx(fewer_honors), rule)


def test_thirteen_unrelated_with_pair(hand):
    rule = RuleConfig(
        patterns=PatternSwitches(
            thirteen_unrelated=ThirteenUnrelatedOptions(
                enabled=True, allow_pair=True, min_gap=3
            )
        )
    )
    tiles = hand("147m147p147s1123z")
    assert is_winning(ctx(tiles), rule)


def test_thirteen_unrelated_pair_rejected_when_not_allowed(hand):
    rule = RuleConfig(
        patterns=PatternSwitches(
            thirteen_unrelated=ThirteenUnrelatedOptions(
                enabled=True, allow_pair=False, min_gap=3
            )
        )
    )
    tiles = hand("147m147p147s1123z")
    assert not is_winning(ctx(tiles), rule)


def test_thirteen_unrelated_disabled_by_default(hand):
    tiles = hand("147m147p1s1234567z")
    assert not is_winning(ctx(tiles), RuleConfig())
