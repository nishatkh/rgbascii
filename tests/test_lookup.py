"""Character lookup tables: mapping, inversion, edge cases."""

from __future__ import annotations

import numpy as np

from rgbascii.processing.lookup import build_char_tables, char_for_luma


def test_dark_maps_to_first_char():
    chars, lut = build_char_tables(" .:-=+*#%@")
    assert char_for_luma(0, chars, lut) == " "


def test_bright_maps_to_last_char():
    chars, lut = build_char_tables(" .:-=+*#%@")
    assert char_for_luma(255, chars, lut) == "@"


def test_monotonic_density():
    charset = " .:-=+*#%@"
    chars, lut = build_char_tables(charset)
    luma_to_index = [int(lut[v]) for v in range(256)]
    assert luma_to_index == sorted(luma_to_index)


def test_invert_swaps_extremes():
    charset = " .:-=+*#%@"
    chars, lut = build_char_tables(charset, invert=True)
    assert char_for_luma(0, chars, lut) == "@"
    assert char_for_luma(255, chars, lut) == " "


def test_single_char_charset():
    chars, lut = build_char_tables("x")
    assert all(char_for_luma(v, chars, lut) == "x" for v in range(256))


def test_dense_charset_has_many_levels():
    from rgbascii.config import CHARSET_DENSE

    chars, lut = build_char_tables(CHARSET_DENSE)
    assert len(chars) > 60
    distinct = len(set(int(lut[v]) for v in range(256)))
    assert distinct > 40


def test_lut_is_uint8_and_full_range():
    _, lut = build_char_tables(" .#")
    assert lut.shape == (256,)
    assert lut.dtype == np.uint8
    assert int(lut.max()) == 2
    assert int(lut.min()) == 0