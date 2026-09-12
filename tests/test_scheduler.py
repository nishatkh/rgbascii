"""Frame scheduler: playhead -> frame index, lateness, and wait behaviour."""

from __future__ import annotations

import time

import pytest

from rgbascii.playback.scheduler import FrameScheduler


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t


def test_target_index_at_zero():
    clock = FakeClock()
    sched = FrameScheduler(30.0, clock)  # type: ignore[arg-type]
    assert sched.target_index(0.0) == 0


def test_target_index_scales_with_time():
    clock = FakeClock()
    sched = FrameScheduler(30.0, clock)  # type: ignore[arg-type]
    clock.t = 1.0
    assert sched.target_index(0.0) == 30
    clock.t = 2.5
    assert sched.target_index(0.0) == 75


def test_segment_start_offsets_index():
    clock = FakeClock()
    sched = FrameScheduler(10.0, clock)  # type: ignore[arg-type]
    clock.t = 25.0
    assert sched.target_index(20.0) == 50


def test_negative_time_is_minus_one():
    clock = FakeClock()
    sched = FrameScheduler(10.0, clock)  # type: ignore[arg-type]
    clock.t = 5.0
    assert sched.target_index(10.0) == -1


def test_is_late():
    clock = FakeClock()
    sched = FrameScheduler(10.0, clock)  # type: ignore[arg-type]
    clock.t = 0.0
    assert not sched.is_late(0, 0.0)
    clock.t = 1.0  # frame 0 + 1 should have been shown by 0.2s
    assert sched.is_late(0, 0.0)


def test_wait_until_frame_sleeps():
    clock = FakeClock()
    sched = FrameScheduler(100.0, clock)  # type: ignore[arg-type]

    # a clock that advances with real time
    class RealClock:
        def __init__(self):
            self.t0 = time.monotonic()

        def now(self):
            return time.monotonic() - self.t0

    real = RealClock()
    sched2 = FrameScheduler(50.0, real)  # type: ignore[arg-type]
    start = time.monotonic()
    sched2.wait_until_frame(2, 0.0, lambda: False)  # should wait ~0.04s
    assert time.monotonic() - start >= 0.02


def test_wait_returns_when_paused():
    clock = FakeClock()
    sched = FrameScheduler(1.0, clock)  # type: ignore[arg-type]
    start = time.monotonic()
    sched.wait_until_frame(100, 0.0, lambda: True)  # paused -> immediate
    assert time.monotonic() - start < 0.1


def test_invalid_fps():
    with pytest.raises(ValueError):
        FrameScheduler(0.0, FakeClock())  # type: ignore[arg-type]


def test_frame_dropping_simulation():
    """A slow renderer must be able to skip indices and land on current ones."""
    clock = FakeClock()
    sched = FrameScheduler(30.0, clock)  # type: ignore[arg-type]

    available = iter(range(0, 300))
    rendered = []
    clock.t = 0.0
    for _ in range(20):
        target = sched.target_index(0.0)
        # simulate 0.1s render time -> 3 frames of drift each loop
        clock.t += 0.1
        frame = next(available)
        while frame < target:
            frame = next(available)  # drop stale
        rendered.append(frame)
    # despite skipping, rendered indices are non-decreasing and track time
    assert rendered == sorted(rendered)
    assert rendered[-1] > 0