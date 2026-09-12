"""ANSI encoding: exact sequences and escape minimization."""

from __future__ import annotations

from rgbascii.rendering.ansi import Raster, encode, plain
from rgbascii.terminal import ansi as term


def test_red_foreground_sequence():
    raster = Raster(chars=["A"], fg=[(255, 0, 0)])
    blob = encode(raster, cols=1).decode()
    assert "\x1b[38;2;255;0;0m" in blob
    assert blob.count("38;2;") == 1


def test_repeated_color_emitted_once():
    raster = Raster(chars=list("AAAA"), fg=[(10, 20, 30)] * 4)
    blob = encode(raster, cols=4).decode()
    assert blob.count("38;2;") == 1


def test_color_changes_emit_new_sequence():
    raster = Raster(chars=list("AB"), fg=[(0, 0, 0), (255, 255, 255)])
    blob = encode(raster, cols=2).decode()
    assert blob.count("38;2;") == 2


def test_single_home_per_frame():
    raster = Raster(chars=list("AB") * 4, fg=[(1, 2, 3)] * 8)
    blob = encode(raster, cols=2).decode()
    assert blob.count(term.HOME) == 1


def test_rows_separated_by_newline_and_erased():
    raster = Raster(chars=list("abcd"), fg=[(1, 2, 3)] * 4)
    blob = encode(raster, cols=2).decode()
    assert "\n" in blob
    assert term.ERASE_LINE in blob


def test_default_cells_use_default_fg():
    raster = Raster(chars=[" ", "A"], fg=[None, (5, 5, 5)])
    blob = encode(raster, cols=2).decode()
    assert term.DEFAULT_FG not in blob  # first cell is default, nothing to reset yet


def test_default_after_color_resets():
    raster = Raster(chars=["A", " "], fg=[(5, 5, 5), None])
    blob = encode(raster, cols=2).decode()
    assert term.DEFAULT_FG in blob


def test_background_encoding():
    raster = Raster(chars=["\u2580"], fg=[(255, 0, 0)], bg=[(0, 0, 255)])
    blob = encode(raster, cols=1).decode()
    assert "\x1b[38;2;255;0;0m" in blob
    assert "\x1b[48;2;0;0;255m" in blob


def test_background_repeat_emitted_once():
    raster = Raster(chars=["\u2580"] * 3, fg=[(1, 1, 1)] * 3, bg=[(2, 2, 2)] * 3)
    blob = encode(raster, cols=3).decode()
    assert blob.count("48;2;") == 1


def test_plain_has_no_color_escapes():
    raster = Raster(chars=list("hello"), fg=[(1, 2, 3)] * 5)
    blob = plain(raster, cols=5).decode()
    assert "38;2;" not in blob
    assert "hello" in blob
    assert term.HOME in blob


def test_empty_raster():
    assert encode(Raster(chars=[], fg=[]), cols=1) == b""
    assert plain(Raster(chars=[], fg=[]), cols=1) == b""