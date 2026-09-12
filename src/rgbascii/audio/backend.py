"""Audio backend abstraction.

The playback engine talks only to the ``AudioBackend`` protocol.  Two
implementations exist:

* ``SoundDeviceBackend`` — real output through PortAudio (optional dependency
  ``sounddevice``), implemented in ``audio.player``.
* ``NullAudioBackend`` — silence: it still *decodes* audio and reports a
  position so the pipeline, drift logic and seek behaviour are exercised
  identically; the master clock then gracefully falls back to wall time.

The factory tries the real backend first and degrades to null with a warning,
so a missing/optional audio library never bricks video playback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class AudioStreamInfo:
    sample_rate: int = 44100
    channels: int = 2
    dtype: str = "float32"


class AudioBackend(Protocol):
    """Minimal contract for an audio output device."""

    def stream_info(self) -> AudioStreamInfo:
        ...

    def start(self, offset: float = 0.0, end: float | None = None) -> None:
        """Begin playback from *offset* seconds (decodes via a source handle)."""
        ...

    def pause(self) -> None:
        """Pause output; position is frozen by the caller's clock."""
        ...

    def resume(self) -> None:
        ...

    def seek(self, seconds: float) -> None:
        """Restart output at *seconds*."""
        ...

    def position(self) -> Optional[float]:
        """Current playback position in seconds of *source* time, if playing."""
        ...

    def stop(self) -> None:
        ...

    @property
    def is_playing(self) -> bool:
        ...

    @property
    def dropped(self) -> int:
        """Number of audio buffers that had to be dropped (underruns)."""
        ...


class NullAudioBackend:
    """Always-playing silent backend anchored to wall time.

    Exists so that ``--no-audio`` and missing-sounddevice runs keep a coherent
    "audio is the master clock" architecture without needing a device.
    """

    def __init__(self) -> None:
        import time

        self._time = time
        self._info = AudioStreamInfo()
        self._playing = False
        self._start_mono = 0.0
        self._seek_offset = 0.0
        self._dropped = 0

    def stream_info(self) -> AudioStreamInfo:
        return self._info

    def start(self, offset: float = 0.0, end: float | None = None) -> None:
        self._seek_offset = offset
        self._start_mono = self._time.monotonic()
        self._playing = True

    def pause(self) -> None:
        self._playing = False

    def resume(self) -> None:
        self._playing = True
        self._start_mono = self._time.monotonic() - self._played_so_far()

    def _played_so_far(self) -> float:
        return self._time.monotonic() - self._start_mono

    def seek(self, seconds: float) -> None:
        self._seek_offset = seconds
        self._start_mono = self._time.monotonic()
        self._playing = True

    def position(self) -> Optional[float]:
        if not self._playing:
            return None
        return self._seek_offset + self._played_so_far()

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def dropped(self) -> int:
        return self._dropped

    def stop(self) -> None:
        self._playing = False


def make_audio(source_path: str, *, enabled: bool, source_rate: int | None = None) -> Optional[AudioBackend]:
    """Factory: build a real audio player when possible, else None.

    Order of preference:
      1. ``enabled=False`` (``--no-audio``) -> None (video clock only).
      2. ``sounddevice`` importable              -> SoundDeviceAudioPlayer.
      3. otherwise                               -> None with a warning.
    """
    if not enabled:
        return None
    try:
        from .player import SoundDeviceAudioPlayer

        return SoundDeviceAudioPlayer(source_path, source_rate=source_rate)
    except ImportError:
        import sys

        print(
            "warning: sounddevice not installed; audio disabled (video-only clock); "
            "install with `pip install rgbascii[audio]`",
            file=sys.stderr,
        )
        return None