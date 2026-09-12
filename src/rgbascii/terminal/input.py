"""Non-blocking keyboard input.

A daemon thread reads from the controlling terminal in raw mode (POSIX
termios) or via msvcrt (Windows) and publishes decoded key events onto a
``queue.Queue`` consumed by the playback loop.  Reading never blocks the
renderer and never writes to stdout, so terminal output stays clean.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from typing import Optional

KeyEvent = str  # one of: 'space','q','p','left','right','+','-','r','resize'


class InputThread:
    """Pushes key events onto ``events``.  Call ``start()``/``stop()``."""

    def __init__(self, events: queue.Queue, *, poll_interval: float = 0.05) -> None:
        self.events = events
        self._poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        try:
            self._fd = getattr(getattr(__import__("sys"), "stdin"), "fileno", lambda: -1)()
        except Exception:
            self._fd = -1

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="rgbascii-input")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    # -- polling --------------------------------------------------------------

    def _run(self) -> None:
        if os.name == "nt":
            self._run_windows()
        else:
            self._run_posix()

    def _run_posix(self) -> None:
        import select
        import termios
        import tty

        try:
            fd = sys.stdin.fileno()
        except (OSError, ValueError, AttributeError):
            self._stop.wait(0.2)
            return
        old = None
        try:
            old = _save_termios(fd)
            tty.setraw(fd)
        except (OSError, AttributeError):  # pragma: no cover - non-tty stdin
            time.sleep(0.2)
            self._stop.wait(0.2)
            return

        prev = time.time()
        try:
            buf = b""
            while not self._stop.is_set():
                r, _, _ = select.select([fd], [], [], self._poll_interval)
                if r:
                    try:
                        buf += os.read(fd, 64)
                    except OSError:
                        break
                now = time.time()
                if now - prev >= 0.25:
                    self.events.put("resize")
                    prev = now
                buf = self._parse(buf)
        finally:
            if old is not None:
                try:
                    termios.tcsetattr(fd, tty.TCSAFLUSH, old)
                except Exception:
                    pass

    def _run_windows(self) -> None:  # pragma: no cover - Windows only
        import msvcrt

        prev = time.time()
        while not self._stop.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    ch2 = msvcrt.getwch()
                    self._emit_arrow(ch2)
                else:
                    self._emit(ch)
            now = time.time()
            if now - prev >= 0.25:
                self.events.put("resize")
                prev = now
            time.sleep(self._poll_interval)

    # -- parsing ----------------------------------------------------------------

    def _parse(self, buf: bytes) -> bytes:
        """Translate raw bytes to key events; return unconsumed remainder."""
        while buf:
            c = buf[0]
            # multi-byte escape sequences: wait for all bytes before parsing
            if c == 0x1B:
                if len(buf) >= 3 and buf[:3] in (b"\x1b[A", b"\x1b[B", b"\x1b[C", b"\x1b[D"):
                    name = {b"\x1b[A": "up", b"\x1b[B": "down", b"\x1b[C": "right", b"\x1b[D": "left"}[buf[:3]]
                    self.events.put(name)
                    buf = buf[3:]
                    continue
                if len(buf) < 3:
                    return buf  # incomplete escape: wait for the rest
                buf = buf[1:]  # lone ESC or unknown sequence: consume
                continue
            if c == 0x03:
                self.events.put("q"); buf = buf[1:]; continue
            if c == 0x20:
                self.events.put("space"); buf = buf[1:]; continue
            if c in (0x71, 0x51):
                self.events.put("q"); buf = buf[1:]; continue
            if c in (0x70, 0x50):
                self.events.put("p"); buf = buf[1:]; continue
            if c in (0x72, 0x52):
                self.events.put("r"); buf = buf[1:]; continue
            if c in (0x2B, 0x3D):
                self.events.put("+"); buf = buf[1:]; continue
            if c == 0x2D:
                self.events.put("-"); buf = buf[1:]; continue
            if c == 0x0D:
                self.events.put("enter"); buf = buf[1:]; continue
            buf = buf[1:]
        return buf

    def _emit(self, ch: str) -> None:  # pragma: no cover - Windows
        name = {
            " ": "space", "\x03": "q", "q": "q", "p": "p", "r": "r",
            "+": "+", "=": "+", "-": "-", "\r": "enter",
        }.get(ch)
        if name:
            self.events.put(name)

    def _emit_arrow(self, ch: str) -> None:  # pragma: no cover - Windows
        name = {"H": "up", "P": "down", "K": "left", "M": "right"}.get(ch)
        if name:
            self.events.put(name)


def _save_termios(fd: int):  # noqa: ANN001 - returns termios list
    import termios

    return termios.tcgetattr(fd)


def drain(events: queue.Queue) -> list[KeyEvent]:
    """Non-blocking drain helper for the playback loop."""
    out: list[KeyEvent] = []
    while True:
        try:
            out.append(events.get_nowait())
        except queue.Empty:
            return out