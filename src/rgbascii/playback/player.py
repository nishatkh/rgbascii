"""Playback engine.

Orchestrates decoder, audio, renderer, terminal, clock, scheduler and input
into one real-time loop.  Responsibilities:

* **frame scheduling** — the renderer is presented frames from the master
  clock's playhead; stale decoded frames are dropped, a sustained decoder lag
  triggers a hard re-seed (`--catchup-ms`);
* **input** — pause/quit/seek/resolution keys plus automatic terminal-resize
  detection, applied without ever touching the output byte stream;
* **end-of-video** — finish or loop;
* **debug** — optional throttle-printed stats to stderr (never interleaved
  with the frame stream).
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Iterator, Optional

import numpy as np

from .. import config as cfgmod
from ..audio.backend import make_audio
from ..errors import EndOfVideo
from ..rendering.base import BaseRenderer
from ..terminal.renderer import TerminalScreen
from ..video.ffmpeg import FFmpegVideoDecoder
from ..video.metadata import VideoMetadata
from . import events
from .clock import PlaybackClock
from .scheduler import FrameScheduler

SEEK_STEP = 5.0
RES_STEP = 4

DEBUG_LABEL = "RGB ASCII Renderer"


@dataclass
class PlaybackStats:
    rendered: int = 0
    dropped: int = 0
    decoded_dropped: int = 0
    rescues: int = 0
    started: float = field(default_factory=time.monotonic)
    last_frame_ts: float = 0.0

    @property
    def elapsed(self) -> float:
        return max(0.001, time.monotonic() - self.started)

    @property
    def fps_actual(self) -> float:
        return self.rendered / self.elapsed


class PlaybackEngine:
    def __init__(
        self,
        cfg: cfgmod.Config,
        meta: VideoMetadata,
        decoder: FFmpegVideoDecoder,
        renderer: BaseRenderer,
        screen: TerminalScreen,
        *,
        debug_out=None,
    ) -> None:
        self.cfg = cfg
        self.meta = meta
        self.decoder = decoder
        self.renderer = renderer
        self.screen = screen
        self.debug_out = debug_out or sys.stderr

        cfg.source_width = meta.width
        cfg.source_height = meta.height

        self.fps = cfg.fps or meta.fps
        self.audio = None
        self.clock = PlaybackClock(self.audio)
        self.scheduler = FrameScheduler(self.fps, self.clock)
        self.stats = PlaybackStats()
        self._gen: Optional[Iterator[tuple[int, np.ndarray]]] = None
        self._base_pts = 0.0
        self._pending: Optional[tuple[int, np.ndarray]] = None
        self._running = True
        self._last_grid = None
        self._grid = None
        self._resize_check = 0.0
        self._paused = False

    # =====================================================================
    # public
    # =====================================================================

    def dur(self) -> float:
        if self.cfg.end is not None:
            return self.cfg.end
        return self.meta.duration if self.meta.duration is not None else float("inf")

    def run(self) -> int:
        self._init_audio()
        self._install_clock()
        start = max(0.0, self.cfg.start)
        self.clock.start(start)
        self._recompute_grid()
        self._seed(start)

        if self.audio is not None:
            try:
                self.audio.start(start, self._end_for_decode())
            except Exception as exc:
                self._warn(f"audio failed to start: {exc}; continuing video-only")
                self.audio = None
                self._install_clock()
                self.clock.start(start)

        self._print_header()

        try:
            while self._running:
                self._process_events()
                if not self._running:
                    break
                if self._paused:
                    self.screen.write(b"")  # keep-alive no-op
                    time.sleep(0.02)
                    continue
                self._tick()
        finally:
            self._shutdown_audio()
            if self.cfg.debug:
                self._print_summary()
        return 0

    # =====================================================================
    # internals
    # =====================================================================

    def _init_audio(self) -> None:
        if not self.meta.has_audio or self.cfg.no_audio:
            self.audio = None
            return
        self.audio = make_audio(self.cfg.input_file, enabled=True, source_rate=self.meta.sample_rate)

    def _install_clock(self) -> None:
        """Pick the master clock honouring ``--clock auto|audio|video``."""
        use_audio = self.audio is not None and self.cfg.clock in (
            cfgmod.ClockSource.AUTO,
            cfgmod.ClockSource.AUDIO,
        )
        self.clock = PlaybackClock(self.audio if use_audio else None)
        self.scheduler = FrameScheduler(self.fps, self.clock)

    def _seed(self, start: float) -> None:
        """(Re)start the video decode from *start* seconds."""
        self._close_gen()
        self._base_pts = start
        self._gen = self.decoder.frames(start=start, end=self._end_for_decode())
        self._pending = None

    def _end_for_decode(self) -> float | None:
        if self.cfg.end is not None:
            return self.cfg.end
        return self.meta.duration

    def _tick(self) -> None:
        sched = self.scheduler
        target = sched.target_index(self._base_pts)

        if target < 0:
            self.scheduler.wait_until_frame(0, self._base_pts, lambda: self._paused or not self._running)
            return

        frame = self._next_renderable(target)
        if frame is None:
            # Nothing available yet.  A loop-reseed may have reset base_pts and
            # the clock, so recompute the wait target from the current state
            # instead of waiting on the stale pre-EOF timeline.
            target = sched.target_index(self._base_pts)
            self.scheduler.wait_until_frame(target, self._base_pts, lambda: self._paused or not self._running)
            return

        idx, rgb = frame
        self._present(idx, rgb)
        self._pending = None  # frame consumed; next tick pulls the following one
        self.scheduler.wait_until_frame(idx + 1, self._base_pts, lambda: self._paused or not self._running)

    def _next_renderable(self, target: int) -> Optional[tuple[int, np.ndarray]]:
        """Fetch, dropping stale decoded frames until we reach *target*."""
        while True:
            if self._pending is None:
                self._pending = self._advance_gen()
                if self._pending is None:
                    return None
            idx, rgb = self._pending
            if idx >= target:
                return (idx, rgb)
            # stale: drop and keep pulling
            self.stats.dropped += 1
            self._pending = None
            lag = self.clock.now() - self.scheduler.time_of(idx, self._base_pts)
            if lag * 1000 > self.cfg.catchup_ms:
                self._rescue()

    def _advance_gen(self) -> Optional[tuple[int, np.ndarray]]:
        if self._gen is None:
            return None
        try:
            idx, rgb = next(self._gen)
            idx = int(idx)
            self._maybe_geometry_check()
            return (idx, rgb)
        except StopIteration:
            return self._handle_end()
        except Exception as exc:  # decoder hiccup is not fatal
            self._warn(f"decoder error: {exc}")
            return self._handle_end()

    def _handle_end(self) -> None:
        self._gen = None
        self._pending = None
        if self.cfg.loop:
            self._reseed(self.cfg.start)
        else:
            self._running = False
        return None

    def _present(self, idx: int, rgb: np.ndarray) -> None:
        blob = self.renderer.render(rgb, self._grid)
        self.screen.write(blob)
        self.stats.rendered += 1
        self.stats.last_frame_ts = time.monotonic()
        self.stats.decoded_dropped = self.decoder.dropped
        if self.cfg.debug:
            self._maybe_debug_line()
        if self.cfg.frames is not None and self.stats.rendered >= self.cfg.frames:
            self._running = False

    # =====================================================================
    # geometry / resize
    # =====================================================================

    def _recompute_grid(self):
        cols, rows = self.screen.cols, self.screen.rows
        self._grid = self.cfg.compute_grid(cols, rows)
        return self._grid

    def _maybe_geometry_check(self) -> None:
        now = time.monotonic()
        if now - self._resize_check < 0.25:
            return
        self._resize_check = now
        try:
            cols, rows = self.screen.cols, self.screen.rows
        except Exception:
            return
        old = self._grid
        new = self.cfg.compute_grid(cols, rows)
        if old is None or old != new:
            self._grid = new

    def _rescue(self) -> None:
        """Hard catch-up: re-seed the decode at the current playhead."""
        self.stats.rescues += 1
        at = self.clock.now()
        at = min(max(at, 0.0), self.dur())
        self._close_gen()
        self._seed(at)

    def _close_gen(self) -> None:
        if self._gen is not None:
            try:
                self._gen.close()
            except Exception:
                pass
            self._gen = None
        self._pending = None

    def _reseed(self, pos: float) -> None:
        self._seed(pos)
        self.clock.seek(pos)
        # Also restart the audio stream so it loops in sync with the video.
        if self.audio is not None:
            try:
                self.audio.seek(pos)
            except Exception as exc:
                self._warn(f"audio reseed failed: {exc}; continuing video-only")

    # =====================================================================
    # input
    # =====================================================================

    def _process_events(self) -> None:
        for ev in events.drain():
            self._on_event(ev)

    def _on_event(self, ev: str) -> None:
        if ev == "q":
            self._running = False
        elif ev in ("space", "p"):
            self._toggle_pause()
        elif ev == "left":
            self._seek(-SEEK_STEP)
        elif ev == "right":
            self._seek(+SEEK_STEP)
        elif ev == "+":
            self._bump_resolution(+RES_STEP)
        elif ev == "-":
            self._bump_resolution(-RES_STEP)
        elif ev == "r":
            self._reseed(self.cfg.start)
        elif ev == "resize":
            self._recompute_grid()

    def _toggle_pause(self) -> None:
        if self._paused:
            self.clock.resume()
            self._paused = False
        else:
            self.clock.pause()
            self._paused = True

    def _seek(self, delta: float) -> None:
        pos = self.clock.now() + delta
        pos = min(max(pos, 0.0), self.dur())
        self._reseed(pos)
        self._paused = False  # seeking resumes playback

    def _bump_resolution(self, delta: int) -> None:
        current = self.cfg.width or self._grid.content_cols if self._grid is not None else 40
        new_w = current + delta
        new_w = min(max(new_w, 8), self.screen.cols)
        self.cfg.width = new_w
        self.cfg.height = None
        self._recompute_grid()

    # =====================================================================
    # audio / teardown
    # =====================================================================

    def _shutdown_audio(self) -> None:
        if self.audio is not None:
            try:
                self.audio.stop()
            except Exception:
                pass

    # =====================================================================
    # debug / status
    # =====================================================================

    def _print_header(self) -> None:
        if not self.cfg.debug:
            return
        m = self.meta
        grid = self._grid
        print(DEBUG_LABEL, file=self.debug_out)
        print("─" * 28, file=self.debug_out)
        print(f"Video       : {self.cfg.input_file}", file=self.debug_out)
        print(f"Resolution  : {m.width}x{m.height}", file=self.debug_out)
        print(f"FPS         : {m.fps:.3g}", file=self.debug_out)
        print(f"Duration    : {fmt_time(m.duration)}", file=self.debug_out)
        print(f"Terminal    : {self.screen.cols}x{self.screen.rows}", file=self.debug_out)
        print(f"Renderer    : {self.cfg.mode.value}", file=self.debug_out)
        print(f"Color       : {'ANSI True Color' if self.cfg.color_enabled else 'off'}", file=self.debug_out)
        print(f"Audio       : {'enabled' if self.audio is not None else 'disabled'}", file=self.debug_out)
        print(f"Target FPS  : {self.fps:.3g}", file=self.debug_out)
        if hasattr(self, "_grid"):
            print(
                f"Grid size   : {grid.content_cols}x{grid.content_rows}"
                + (f" (letterbox {grid.cols}x{grid.rows})" if grid.is_letterboxed else ""),
                file=self.debug_out,
            )
        print(file=self.debug_out)
        self.debug_out.flush()

    def _maybe_debug_line(self) -> None:
        now = time.monotonic()
        marker = getattr(self, "_last_debug", 0.0)
        if now - marker < 1.0:
            return
        self._last_debug = now
        pos = self.clock.now()
        line = (
            f"[{fmt_time(pos)}/{fmt_time(self.dur())}] "
            f"fps={self.stats.fps_actual:5.2f} rendered={self.stats.rendered} "
            f"dropped={self.stats.dropped} rescued={self.stats.rescues}"
            + (" paused" if self._paused else "")
        )
        print(f"\r{line:<70}", file=self.debug_out, end="")
        self.debug_out.flush()

    def _print_summary(self) -> None:
        self.debug_out.flush()
        print(file=self.debug_out)
        print("─" * 28, file=self.debug_out)
        print(f"Frames       : {self.stats.rendered}", file=self.debug_out)
        print(f"Actual FPS   : {self.stats.fps_actual:.3f}", file=self.debug_out)
        print(f"Dropped      : {self.stats.dropped}", file=self.debug_out)
        print(f"Decoded drop : {self.stats.decoded_dropped}", file=self.debug_out)
        print(f"Rescues      : {self.stats.rescues}", file=self.debug_out)
        print(f"Elapsed      : {self.stats.elapsed:.1f}s", file=self.debug_out)
        self.debug_out.flush()

    def _warn(self, message: str) -> None:
        print(f"warning: {message}", file=self.debug_out)
        self.debug_out.flush()


def fmt_time(seconds: float | None) -> str:
    if seconds is None or seconds == float("inf"):
        return "--:--"
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"