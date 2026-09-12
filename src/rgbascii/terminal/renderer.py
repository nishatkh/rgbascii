"""Terminal screen: a small abstraction over the raw byte stream.

Owns cursor visibility, the alternate screen buffer, and the single output
buffered writer.  All writes go through one ``os.write`` per frame so the
frame never interleaves with anything else.  ``__enter__``/``__exit__``
guarantee the terminal is restored on normal return, Ctrl+C, or exception.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Optional

from ..playback import events
from . import ansi
from . import size as size_mod
from .input import InputThread


class TerminalScreen:
    def __init__(self, *, fullscreen: bool = True, use_raw_input: bool = True) -> None:
        self.fullscreen = fullscreen
        self._use_raw_input = use_raw_input
        self._write_lock = threading.Lock()
        self._out = sys.stdout.buffer
        self._fd = self._out.fileno() if hasattr(self._out, "fileno") else None
        self._input: Optional[InputThread] = None
        self.geometry: tuple[int, int] = (0, 0)

    # -- lifecycle -------------------------------------------------------------

    def __enter__(self) -> "TerminalScreen":
        if sys.stdout.isatty():
            self._enter_raw_mode()
        self._emit(ansi.HIDE_CURSOR)
        if self.fullscreen:
            self._emit(ansi.ALT_SCREEN_ON + ansi.CLEAR)
        else:
            self._emit(ansi.CLEAR + ansi.HOME)
        self.refresh_geometry()
        if self._use_raw_input:
            self._input = InputThread(events.event_queue)
            self._input.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self._quit()

    def _quit(self) -> None:
        if self._input is not None:
            self._input.stop()
            self._input = None
        try:
            self._emit(ansi.RESET + ansi.SHOW_CURSOR)
            if self.fullscreen:
                self._emit(ansi.ALT_SCREEN_OFF)
        except Exception:
            pass
        self._restore_raw_mode()
        self._flush()

    # -- output ------------------------------------------------------------------

    def write(self, data: bytes) -> None:
        with self._write_lock:
            if self._fd is not None:
                os.write(self._fd, data)
            else:
                self._out.write(data)
                self._out.flush()

    def _emit(self, text: str) -> None:
        self.write(text.encode("utf-8", "replace"))

    def _flush(self) -> None:
        with self._write_lock:
            self._out.flush()

    # -- geometry ------------------------------------------------------------------

    def refresh_geometry(self) -> None:
        self.geometry = size_mod.get_terminal_size()

    @property
    def cols(self) -> int:
        return self.geometry[0]

    @property
    def rows(self) -> int:
        return self.geometry[1]

    # -- raw mode -----------------------------------------------------------------

    def _enter_raw_mode(self) -> None:  # pragma: no cover - env specific
        if os.name == "nt":
            return
        try:
            import termios
            import tty

            self._fd_in = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd_in)
            tty.setcbreak(self._fd_in)
        except Exception:
            self._fd_in = None
            self._old = None

    def _restore_raw_mode(self) -> None:  # pragma: no cover - env specific
        if getattr(self, "_fd_in", None) is None or getattr(self, "_old", None) is None:
            return
        try:
            import termios

            termios.tcsetattr(self._fd_in, termios.TCSADRAIN, self._old)
        except Exception:
            pass