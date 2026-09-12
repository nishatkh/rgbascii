"""Grayscale renderer.

Same glyph selection as the colour renderer, but the foreground is a neutral
grey built from the same perceptual luminance value.  Implementation reuses
the full-colour composition and only overrides the colour policy hook.
"""

from __future__ import annotations

from .ascii import AsciiRenderer
from .base import RGB


class GrayscaleRenderer(AsciiRenderer):
    CELL_H = 1

    def _cell_color(self, luma: int, _rgb: list[int]) -> RGB:
        return (luma, luma, luma)