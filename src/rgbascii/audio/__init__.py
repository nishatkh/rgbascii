"""Audio package: backend protocol, silent fallback, and sounddevice-based
player.  Public entry point is ``backend.make_audio``."""

from __future__ import annotations

from .backend import AudioBackend, AudioStreamInfo, NullAudioBackend, make_audio

__all__ = ["AudioBackend", "AudioStreamInfo", "NullAudioBackend", "make_audio"]