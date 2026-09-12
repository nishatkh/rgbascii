"""Playback clock: wall and audio masters, pause/resume, seek."""

from __future__ import annotations

import time

from rgbascii.audio.backend import NullAudioBackend
from rgbascii.playback.clock import PlaybackClock


class FakeAudio:
    """Controllable audio backend for deterministic clock tests."""

    def __init__(self) -> None:
        self._pos = 0.0
        self._playing = False
        self.paused = False
        self.seek_to = 0.0

    def start(self, offset=0.0, end=None):
        self._pos = offset
        self._playing = True

    def position(self):
        return self._pos if self._playing else None

    def set_pos(self, value):
        self._pos = value

    def pause(self):
        self._playing = False

    def resume(self):
        self._playing = True

    def seek(self, seconds):
        self._pos = seconds
        self._playing = True
        self.paused = True

    def stop(self):
        self._playing = False

    @property
    def is_playing(self):
        return self._playing

    @property
    def dropped(self):
        return 0


def test_wall_clock_advances():
    clock = PlaybackClock(None)
    clock.start(0.0)
    time.sleep(0.05)
    assert clock.now() >= 0.04


def test_wall_clock_offset():
    clock = PlaybackClock(None)
    clock.start(30.0)
    assert 30.0 <= clock.now() < 30.2


def test_audio_clock_uses_audio_position():
    audio = FakeAudio()
    audio.start(10.0)
    clock = PlaybackClock(audio)
    clock.start(0.0)
    audio.set_pos(12.5)
    assert clock.now() == 12.5


def test_pause_freezes_position():
    audio = FakeAudio()
    audio.start(5.0)
    clock = PlaybackClock(audio)
    clock.start(0.0)
    audio.set_pos(6.0)
    clock.pause()
    audio.set_pos(9.0)  # device keeps counting silence
    assert clock.now() == 6.0


def test_resume_removes_pause_debt():
    audio = FakeAudio()
    audio.start(5.0)
    clock = PlaybackClock(audio)
    clock.start(0.0)
    audio.set_pos(6.0)
    clock.pause()
    audio.set_pos(9.0)  # 3 seconds of silence
    clock.resume()
    # raw position is 9.0 but 3s of silence must be subtracted
    assert clock.now() == 6.0


def test_seek_resets_clock():
    audio = FakeAudio()
    audio.start(0.0)
    clock = PlaybackClock(audio)
    clock.start(0.0)
    clock.seek(40.0)
    assert clock.now() == 40.0
    assert audio.position() == 40.0


def test_wall_clock_seek():
    clock = PlaybackClock(None)
    clock.start(0.0)
    clock.seek(12.0)
    assert 12.0 <= clock.now() < 12.2


def test_null_audio_advances_with_wall_time():
    null = NullAudioBackend()
    null.start()
    time.sleep(0.05)
    assert null.position() >= 0.04
    null.pause()
    paused_at = null.position()
    time.sleep(0.02)
    assert null.position() == paused_at