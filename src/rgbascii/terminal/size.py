"""Terminal dimension detection, cross-platform.

Primary source is ``shutil.get_terminal_size`` which falls back to ANSI probe
then built-in defaults.  On platforms where the OS keeps the size fresh only
after a signal, the player is responsible for re-polling each iteration.
"""

from __future__ import annotations

import os
import shutil
import sys

MIN_COLS = 20
MIN_ROWS = 6

_default_size: tuple[int, int] | None = None


def set_default_size(cols: int, rows: int) -> None:
    global _default_size
    _default_size = (cols, rows)


def get_terminal_size() -> tuple[int, int]:
    """Return ``(cols, rows)`` of the controlling terminal.

    Raises ``TerminalError`` if the size cannot be determined and no sensible
    default is available (non-interactive session).
    """
    if os.name == "nt":
        size = _windows_size() or shutil.get_terminal_size(fallback=(80, 24))
        return _guarded(size.columns, size.lines)
    size = shutil.get_terminal_size(fallback=(80, 24))
    cols, rows = size.columns, size.lines
    if cols == 0 or rows == 0 or (cols == 80 and rows == 24 and not sys.stdout.isatty()):
        if _default_size is not None:
            cols, rows = _default_size
    return _guarded(cols, rows)


def _guarded(cols: int, rows: int) -> tuple[int, int]:
    if cols < MIN_COLS or rows < MIN_ROWS:
        from ..errors import TerminalError

        raise TerminalError(
            f"terminal is too small ({cols}x{rows}); need at least {MIN_COLS}x{MIN_ROWS} "
            "(resize or pass --width/--height)"
        )
    return int(cols), int(rows)


def _windows_size():  # pragma: no cover - Windows only
    try:
        import ctypes

        class _CSIZE(ctypes.Structure):
            _fields_ = [("rows", ctypes.c_short), ("cols", ctypes.c_short)]

        h = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        cs = _CSIZE()
        if ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h, ctypes.byref(cs)):
            # fields are swapped in CONSOLE_SCREEN_BUFFER_INFO on modern shells
            return type("T", (), {"columns": max(cs.cols, cs.rows), "lines": max(cs.rows, cs.cols)})()
    except Exception:
        return None
    return None