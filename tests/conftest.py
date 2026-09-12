"""Shared test fixtures and synthetic frame generators.

Everything the tests need is generated deterministically so no external media
file is required for unit testing.  The only integration tests that need real
video use ffmpeg to synthesise a clip in a session-scoped tmp dir.
"""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# synthetic frames
# ---------------------------------------------------------------------------


def solid(rgb: tuple[int, int, int], h: int = 32, w: int = 48) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, :] = np.array(rgb, dtype=np.uint8)
    return frame


def gradient(h: int = 32, w: int = 48) -> np.ndarray:
    x = np.linspace(0, 255, w, dtype=np.uint8)
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, :, 0] = x[None, :]
    frame[:, :, 1] = x[None, :]
    frame[:, :, 2] = x[None, :]
    return frame


def checkerboard(h: int = 32, w: int = 48, cell: int = 4) -> np.ndarray:
    ys = (np.arange(h) // cell)[:, None]
    xs = (np.arange(w) // cell)[None, :]
    mask = ((ys + xs) % 2).astype(np.uint8) * 255
    frame = np.repeat(mask[:, :, None], 3, axis=2)
    return frame


@pytest.fixture
def black_frame() -> np.ndarray:
    return solid((0, 0, 0))


@pytest.fixture
def white_frame() -> np.ndarray:
    return solid((255, 255, 255))


@pytest.fixture
def red_frame() -> np.ndarray:
    return solid((255, 0, 0))


# ---------------------------------------------------------------------------
# ffmpeg integration fixtures
# ---------------------------------------------------------------------------

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not installed")


@pytest.fixture(autouse=True)
def _clean_event_queue():
    """The shared input queue is a module global; keep tests independent."""
    from rgbascii.playback import events

    events.drain()
    yield
    events.drain()


@pytest.fixture(scope="session")
def synthetic_video(tmp_path_factory):
    """A 2-second 160x120 24fps test clip with a moving square, + tone audio."""
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg not installed")
    out = tmp_path_factory.mktemp("video") / "test.mp4"
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-shortest",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        pytest.skip(f"could not synthesise test video: {proc.stderr[-300:]}")
    return str(out)


@pytest.fixture(scope="session")
def silent_video(tmp_path_factory):
    """A 1-second silent 96x64 clip for video-only decode tests."""
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg not installed")
    out = tmp_path_factory.mktemp("video") / "silent.mp4"
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=96x64:rate=15:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-an",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        pytest.skip(f"could not synthesise silent video: {proc.stderr[-300:]}")
    return str(out)