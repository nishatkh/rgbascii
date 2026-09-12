"""Terminal layer: size detection and input byte parsing (no real tty needed)."""

from __future__ import annotations

import queue

import pytest

from rgbascii.errors import TerminalError
from rgbascii.terminal import size as size_mod
from rgbascii.terminal.input import InputThread


def test_parse_arrow_keys():
    q: queue.Queue = queue.Queue()
    reader = InputThread(q)
    reader._parse(b"\x1b[D\x1b[C")
    assert q.get_nowait() == "left"
    assert q.get_nowait() == "right"


def test_parse_space_and_quit():
    q: queue.Queue = queue.Queue()
    reader = InputThread(q)
    reader._parse(b" q")
    assert q.get_nowait() == "space"
    assert q.get_nowait() == "q"


def test_parse_plus_minus():
    q: queue.Queue = queue.Queue()
    reader = InputThread(q)
    reader._parse(b"+=-")
    assert q.get_nowait() == "+"
    assert q.get_nowait() == "+"
    assert q.get_nowait() == "-"


def test_parse_ctrl_c_is_quit():
    q: queue.Queue = queue.Queue()
    reader = InputThread(q)
    reader._parse(b"\x03")
    assert q.get_nowait() == "q"


def test_parse_partial_escape_buffer_retained():
    q: queue.Queue = queue.Queue()
    reader = InputThread(q)
    remainder = reader._parse(b"\x1b[")
    assert remainder == b"\x1b["
    remainder = reader._parse(remainder + b"D")
    assert q.get_nowait() == "left"
    assert remainder == b""


def test_unknown_bytes_ignored():
    q: queue.Queue = queue.Queue()
    reader = InputThread(q)
    reader._parse(b"\x01\x02")
    assert q.empty()


def test_size_guard_rejects_tiny():
    with pytest.raises(TerminalError):
        size_mod._guarded(10, 3)


def test_size_guard_accepts_normal():
    assert size_mod._guarded(80, 24) == (80, 24)


def test_get_terminal_size_returns_positive():
    cols, rows = size_mod.get_terminal_size()
    assert cols >= size_mod.MIN_COLS
    assert rows >= size_mod.MIN_ROWS