from collections import Counter

from game.tiles import (
    TILE_KINDS,
    WALL_SIZE,
    counts_from_tiles,
    is_honor,
    is_suit,
    new_wall,
    tile_name,
    tiles_from_counts,
)


def test_wall_has_136_tiles_and_four_of_each():
    wall = new_wall()
    assert len(wall) == WALL_SIZE == 136
    counter = Counter(wall)
    assert len(counter) == TILE_KINDS
    assert all(count == 4 for count in counter.values())


def test_tile_names():
    assert tile_name(0) == "一万"
    assert tile_name(8) == "九万"
    assert tile_name(9) == "一筒"
    assert tile_name(26) == "九条"
    assert tile_name(27) == "东"
    assert tile_name(33) == "白"


def test_suit_and_honor_detection():
    assert is_suit(0) and is_suit(26)
    assert not is_suit(27)
    assert is_honor(27) and is_honor(33)
    assert not is_honor(0)


def test_counts_round_trip():
    tiles = [0, 0, 5, 27, 33]
    counts = counts_from_tiles(tiles)
    assert counts[0] == 2
    assert counts[5] == 1
    assert counts[27] == 1
    assert sorted(tiles_from_counts(counts)) == sorted(tiles)


def test_wall_shuffle_keeps_every_tile():
    first = Counter(new_wall())
    second = Counter(new_wall())
    assert first == second
