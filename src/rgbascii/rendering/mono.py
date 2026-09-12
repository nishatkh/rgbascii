"""Monochrome renderer.

A single fixed colour for the entire frame (``--mono-color``), with glyphs
still driven by luminance so the image remains readable.
"""

from __future__ import annotations

from .ascii import AsciiRenderer
from .base import RGB


class MonoRenderer(AsciiRenderer):
    CELL_H = 1

    def __init__(self, cfg) -> None:
        super().__init__(cfg)
        self._fixed: RGB = cfg.mono_color
        if not self._colored:
            self._fixed = (255, 255, 255)

    def _cell_color(self, _luma: int, _rgb: list[int]) -> RGB:
        return self._fixed