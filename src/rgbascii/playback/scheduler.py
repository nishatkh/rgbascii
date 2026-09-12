"""Frame scheduler.

Implementation of the `floor(now * fps)` model: the playhead is the master
clock, and the frame we *want* right now is simply
``floor((now - segment_start) * fps)``.  Forward progress is capped by the
video's natural cadence, not by how long rendering happened to take, and the
caller is given enough information to drop stale frames instead of drowning.

The scheduler is deliberately procedural and stateless — the player owns the
frame loop; this module owns only the *decision* helpers.
"""

from __future__ import annotations

import time

from .clock import PlaybackClock


class FrameScheduler:
    def __init__(self, fps: float, clock: PlaybackClock, *, resolution: float = 0.02) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.fps = float(fps)
        self.clock = clock
        self.resolution = resolution
        self.frame_time = 1.0 / self.fps

    # -- decisions ------------------------------------------------------------

    def target_index(self, segment_start: float) -> int:
        """The absolute frame index the playhead currently wants."""
        pos = self.clock.now() - segment_start
        if pos < 0:
            return -1
        return int(pos * self.fps)

    def time_of(self, index: int, segment_start: float) -> float:
        return segment_start + index * self.frame_time

    def is_late(self, index: int, segment_start: float, tolerance: float = 0.0) -> bool:
        return self.clock.now() > self.time_of(index + 1, segment_start) + tolerance

    # -- waiting --------------------------------------------------------------

    def wait_until_frame(self, index: int, segment_start: float, is_paused) -> None:
        """Sleep (in small slices) until frame *index* is due.

        Slices are bounded by ``self.resolution`` so pause/quit/seek stay
        responsive even during a normal wait.
        """
        due = self.time_of(index, segment_start)
        while True:
            if is_paused():
                return
            now = self.clock.now()
            remaining = due - now
            if remaining <= 0.0:
                return
            time.sleep(min(remaining, self.resolution))