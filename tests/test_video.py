"""FFmpeg decoder and end-to-end playback integration.

These tests require ``ffmpeg``/``ffprobe`` and are skipped otherwise.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import requires_ffmpeg
from rgbascii.config import Config, RenderMode
from rgbascii.playback import events
from rgbascii.rendering import build_renderer
from rgbascii.video.ffmpeg import FFmpegVideoDecoder, parse_rational, probe_metadata


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------


def test_parse_rational():
    assert parse_rational("30000/1001") == pytest.approx(29.97, abs=0.01)
    assert parse_rational("24") == 24.0
    assert parse_rational(None, 30.0) == 30.0
    assert parse_rational("bogus", 12.0) == 12.0


@requires_ffmpeg
def test_probe_metadata(synthetic_video):
    meta = probe_metadata(synthetic_video)
    assert (meta.width, meta.height) == (160, 120)
    assert meta.fps == pytest.approx(24, abs=0.5)
    assert meta.has_audio is True
    assert meta.duration == pytest.approx(2.0, abs=0.3)


@requires_ffmpeg
def test_probe_silent(silent_video):
    meta = probe_metadata(silent_video)
    assert meta.has_audio is False


# ---------------------------------------------------------------------------
# decoding
# ---------------------------------------------------------------------------


@requires_ffmpeg
def test_decoder_streams_correct_frames(silent_video):
    decoder = FFmpegVideoDecoder(silent_video, target_fps=None)
    frames = []
    for idx, frame in decoder.frames():
        assert frame.shape[2] == 3
        assert frame.dtype == np.uint8
        frames.append(idx)
        if len(frames) >= 5:
            break
    decoder.stop()
    assert frames == list(range(len(frames)))


@requires_ffmpeg
def test_decoder_restart_reseeds(silent_video):
    decoder = FFmpegVideoDecoder(silent_video, target_fps=None)
    gen = decoder.frames()
    first = next(gen)
    assert first[0] == 0
    decoder.restart(0.5)
    gen2 = decoder.frames(start=0.5)
    idx2, _ = next(gen2)
    decoder.stop()
    assert idx2 >= 1  # index is absolute to the 0.5s seek


# ---------------------------------------------------------------------------
# end-to-end playback through the engine
# ---------------------------------------------------------------------------


class FakeScreen:
    def __init__(self, cols=80, rows=24):
        self.geometry = (cols, rows)
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        if data:
            self.chunks.append(data)

    @property
    def cols(self):
        return self.geometry[0]

    @property
    def rows(self):
        return self.geometry[1]

    def refresh_geometry(self):
        pass


@requires_ffmpeg
@pytest.mark.parametrize("mode", [RenderMode.ASCII, RenderMode.GRAYSCALE, RenderMode.MONO, RenderMode.HALFBLOCK])
def test_playback_engine_renders_frames(silent_video, mode):
    from rgbascii.playback.player import PlaybackEngine

    cfg = Config(input_file=silent_video, width=40, height=12, mode=mode, color=True, frames=6, no_audio=True)
    cfg.source_width, cfg.source_height = 96, 64
    meta = probe_metadata(silent_video)
    decoder = FFmpegVideoDecoder(silent_video, cfg.fps)
    renderer = build_renderer(cfg)
    screen = FakeScreen()
    engine = PlaybackEngine(cfg, meta, decoder, renderer, screen)
    assert engine.run() == 0
    assert len(screen.chunks) >= 1
    assert engine.stats.rendered == 6


@requires_ffmpeg
def test_playback_pause_and_quit_events(silent_video):
    from rgbascii.playback.player import PlaybackEngine

    cfg = Config(input_file=silent_video, width=30, height=10, color=False, frames=4, no_audio=True)
    cfg.source_width, cfg.source_height = 96, 64
    meta = probe_metadata(silent_video)
    decoder = FFmpegVideoDecoder(silent_video, cfg.fps)
    renderer = build_renderer(cfg)
    screen = FakeScreen()
    engine = PlaybackEngine(cfg, meta, decoder, renderer, screen)

    events.event_queue.put("space")
    engine._process_events()
    assert engine._paused is True
    events.event_queue.put("space")
    engine._process_events()
    assert engine._paused is False

    events.event_queue.put("q")
    engine._process_events()
    assert engine._running is False


@requires_ffmpeg
def test_quit_during_run(silent_video):
    from rgbascii.playback.player import PlaybackEngine

    cfg = Config(input_file=silent_video, width=30, height=10, color=False, no_audio=True)
    cfg.source_width, cfg.source_height = 96, 64
    meta = probe_metadata(silent_video)
    decoder = FFmpegVideoDecoder(silent_video, cfg.fps)
    renderer = build_renderer(cfg)
    screen = FakeScreen()
    engine = PlaybackEngine(cfg, meta, decoder, renderer, screen)
    events.event_queue.put("q")
    assert engine.run() == 0


@requires_ffmpeg
def test_playback_engine_loops_past_eof(silent_video):
    """Verify that --loop resets the clock cleanly and renders past the first EOF."""
    from rgbascii.playback.player import PlaybackEngine

    meta = probe_metadata(silent_video)
    # silent_video ≈ 15 fps, 2 s, 30 frames.
    # Request 50 rendered frames; the loop must break past the first 30.
    cfg = Config(input_file=silent_video, width=30, height=10, color=True, no_audio=True, loop=True, frames=50)
    cfg.source_width, cfg.source_height = 96, 64
    decoder = FFmpegVideoDecoder(silent_video, cfg.fps, queue_size=8)
    renderer = build_renderer(cfg)
    screen = FakeScreen()
    engine = PlaybackEngine(cfg, meta, decoder, renderer, screen)
    assert engine.run() == 0
    assert engine.stats.rendered == 50
    assert engine.stats.dropped == 0