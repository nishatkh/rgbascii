"""Full-colour ASCII renderer.

One terminal cell == one sampled RGB pixel.  The glyph is chosen purely from
perceptual luminance; the foreground colour carries the pixel's RGB.  This is
also the home of the `rgb` mode alias.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .ansi import Raster
from .base import BaseRenderer, RGB


class AsciiRenderer(BaseRenderer):
    CELL_H = 1

    def _compose(self, sample_rgb: np.ndarray, content_cols: int) -> Raster:
        luma = self._luma(sample_rgb)
        lut_idx = self._lut[luma].reshape(-1).tolist()
        luma_flat = luma.reshape(-1).tolist()
        colors: list[list[int]] = sample_rgb.reshape(-1, 3).tolist()

        chars: list[str] = []
        fg: list[Optional[RGB]] = []
        for idx, lum, col in zip(lut_idx, luma_flat, colors):
            chars.append(self._chars[idx])
            fg.append(self._cell_color(lum, col))

        return Raster(chars=chars, fg=fg, bg=None)

    def _cell_color(self, luma: int, rgb: list[int]) -> RGB:
        """Colour policy hook: how a sampled cell maps to a foreground RGB."""
        return (rgb[0], rgb[1], rgb[2])