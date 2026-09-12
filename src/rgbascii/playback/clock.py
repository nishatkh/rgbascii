"""Master playback clock.

The clock answers one question: *what is the current media position, in
seconds?*  The rule is simple — audio is the master clock when it is playing
(PortAudio sample clock, latency-compensated), otherwise wall time.  This is
what keeps audio and video synced regardless of how long rendering takes.

Pausing is honoured per source:

* wall-clock mode: freeze the reported position;
* audio mode: the device keeps counting output samples (they are silence, so
  the listener perceives a freeze).  On resume we measure how many samples
  were "wasted" in the pause and subtract them from the reported position, so
  media position never drifts across pause/resume.
"""

from __future__ import annotations

import time
from typing import Optional

from ..audio.backend import AudioBackend


class PlaybackClock:
    def __init__(self, audio: Optional[AudioBackend]) -> None:
        self._audio = audio
        self._wall_offset = 0.0       # position at wall-time base
        self._base_mono = time.monotonic()
        self._paused = False
        self._frozen = 0.0            # position while paused
        self._debt = 0.0              # silence emitted during pauses (audio mode)
        self._raw_at_pause = 0.0

    def start(self, pos0: float) -> None:
        self._wall_offset = pos0
        self._base_mono = time.monotonic()
        self._debt = 0.0
        self._paused = False

    def now(self) -> float:
        if self._paused:
            return self._frozen
        p = self._audio_now()
        if p is not None:
            return max(0.0, p - self._debt)
        return self._wall_offset + (time.monotonic() - self._base_mono)

    def _audio_now(self) -> Optional[float]:
        if self._audio is None or not getattr(self._audio, "is_playing", False):
            return None
        pos = self._audio.position()
        return pos

    # -- control ------------------------------------------------------------

    def pause(self) -> None:
        if self._paused:
            return
        self._frozen = self.now()
        self._paused = True
        if self._audio is not None:
            self._raw_at_pause = self._audio.position()
        if self._raw_at_pause is None:
            self._raw_at_pause = self._frozen

    def resume(self) -> None:
        if not self._paused:
            return
        if self._audio is not None and getattr(self._audio, "is_playing", False):
            raw_now = self._audio.position() or self._frozen
            self._debt += max(0.0, raw_now - self._raw_at_pause)
            self._audio.resume()
        else:
            self._wall_offset = self._frozen
            self._base_mono = time.monotonic()
        self._paused = False

    def seek(self, pos: float) -> None:
        self._frozen = max(0.0, pos)
        self._wall_offset = self._frozen
        self._base_mono = time.monotonic()
        self._debt = 0.0
        if self._audio is not None:
            self._audio.seek(self._frozen)
            self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def using_audio(self) -> bool:
        return self._audio is not None