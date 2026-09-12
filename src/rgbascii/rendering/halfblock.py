"""RGB half-block renderer.

Uses the Unicode half-block glyph ``U+2580`` (solid top half) so a single
terminal cell renders **two** source pixel rows: the glyph colour paints the
top half and the cell background paints the bottom half.  This doubles the
vertical sampling resolution of the ASCII renderers at no extra screen cost.

Optimization: a cell whose top and bottom colours are equal collapses to a
space with a single background colour (one escape instead of two).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .ansi import Raster
from .base import BaseRenderer, RGB

TOP_BLOCK = "\u2580"
SPACE = " "


class HalfBlockRenderer(BaseRenderer):
    CELL_H = 2

    def _compose(self, sample_rgb: np.ndarray, content_cols: int) -> Raster:
        rows2, cols, _ = sample_rgb.shape  # rows2 == content_rows * 2
        top = sample_rgb[0::2]
        bot = sample_rgb[1::2]

        top_flat: list[list[int]] = top.reshape(-1, 3).tolist()
        bot_flat: list[list[int]] = bot.reshape(-1, 3).tolist()

        chars: list[str] = []
        fg: list[Optional[RGB]] = []
        bg: list[Optional[RGB]] = []
        for t, b in zip(top_flat, bot_flat):
            tcol = (t[0], t[1], t[2])
            bcol = (b[0], b[1], b[2])
            if tcol == bcol:
                chars.append(SPACE)
                fg.append(None)
                bg.append(bcol)
            else:
                chars.append(TOP_BLOCK)
                fg.append(tcol)
                bg.append(bcol)

        return Raster(chars=chars, fg=fg, bg=bg)