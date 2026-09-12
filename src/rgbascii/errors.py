"""Shared exceptions for rgbascii.

Keeping them in one place lets the CLI translate any failure into a single,
concise user-facing message instead of a raw traceback.
"""

from __future__ import annotations


class RgbasciiError(Exception):
    """Base class for all rgbascii errors."""


class VideoError(RgbasciiError):
    """A video could not be probed or decoded."""


class AudioError(RgbasciiError):
    """Audio decoding or playback failed."""


class TerminalError(RgbasciiError):
    """The terminal is unusable (too small, not interactive, ...)."""


class ConfigError(RgbasciiError):
    """Invalid configuration or command-line options."""


class FfmpegNotFoundError(VideoError):
    """ffmpeg / ffprobe binaries could not be found on PATH."""


class EndOfVideo(RgbasciiError):
    """Internal signal: the current playthrough has finished."""

    def __init__(self, frame_index: int = 0) -> None:
        super().__init__("end of video")
        self.frame_index = frame_index