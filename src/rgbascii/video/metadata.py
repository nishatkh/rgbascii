"""Video metadata dataclass, decoupled from any specific backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    frame_count: Optional[int]
    duration: float | None
    sample_rate: int | None = None
    has_audio: bool = False
    codec: str = "unknown"

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0