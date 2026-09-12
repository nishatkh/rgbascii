"""Decoder abstraction.

The ``VideoDecoder`` protocol is a minimal contract that any backend (FFmpeg,
GStreamer, a direct read from `.npy` files, etc.) can satisfy.  The playback
engine depends only on this interface so swapping backends is mechanical.
"""

from __future__ import annotations

from typing import Iterator, Optional, Protocol

import numpy as np

from .metadata import VideoMetadata


class VideoDecoder(Protocol):
    """Abstract video decoder."""

    def metadata(self) -> VideoMetadata:
        """Return metadata about the media *without* decoding any frames."""
        ...

    def frames(self, *, start: float = 0.0, end: float | None = None) -> Iterator[tuple[int, np.ndarray]]:
        """Yield ``(absolute_index, rgb_frame)`` pairs.

        The first frame yielded is ``index=0`` regardless of ``start`` (the
        seek is handled internally).  The generator ends at EOF or when
        ``end`` is reached.
        """
        ...

    def restart(self, at_seconds: float = 0.0) -> None:
        """Kill the current decode and start fresh at *at_seconds*."""
        ...

    def stop(self) -> None:
        """Release all resources immediately."""
        ...