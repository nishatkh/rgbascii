"""Renderer base class.

`BaseRenderer` owns the full shared pipeline so the public renderers stay
thin: resize -> colour adjustment -> luminance -> character/colour selection
-> letterbox padding -> ANSI raster.  Subclasses only implement `_compose`,
the policy that turns the sampled colour buffer into per-cell glyphs and
colours; everything else is inherited.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .. import config
from ..processing import color as colmod
from ..processing import lookup as lookmod
from ..processing import luminance as lummod
from ..processing import resize as resizemod
from .ansi import Raster, encode as encode_raster, plain as encode_plain

RGB = tuple[int, int, int]


class BaseRenderer:
    #: vertical source samples consumed by one terminal cell (1 = ascii, 2 = half-block)
    CELL_H = 1

    def __init__(self, cfg: config.Config) -> None:
        self.cfg = cfg
        charset = cfg.resolve_charset()
        self._chars, self._lut = lookmod.build_char_tables(charset, invert=cfg.invert)
        self._adjuster = colmod.ColorAdjuster(
            levels=cfg.color_levels,
            brightness=cfg.brightness,
            contrast=cfg.contrast,
            saturation=cfg.saturation,
            gamma=cfg.gamma,
        )
        self._colored = cfg.color_enabled

    # -- licence to override --------------------------------------------------

    def _compose(self, sample_rgb: np.ndarray, content_cols: int) -> Raster:
        """Turn the sampled `(rows*CELL_H, content_cols, 3)` buffer into a
        content-only raster (flat, length `rows * content_cols`)."""
        raise NotImplementedError

    # -- shared pipeline ------------------------------------------------------

    def render(self, frame: np.ndarray, grid: config.GridPlan) -> bytes:
        """Render one ``(H, W, 3)`` uint8 RGB frame into a full-frame ANSI blob."""
        sample_w = grid.content_cols
        sample_h = grid.content_rows * self.CELL_H
        if sample_w <= 0 or sample_h <= 0:
            return self._blank_frame(grid)

        method = "average" if self.cfg.sample != config.SampleMethod.CENTER else "nearest"
        sized = resizemod.resize(frame, sample_w, sample_h, method=method)
        sized = self._adjuster.apply(sized)

        content = self._compose(sized, content_cols=sample_w)
        full = self._pad(content, grid)
        if self._colored:
            return encode_raster(full, grid.cols)
        return encode_plain(full, grid.cols)

    # -- shared helpers --------------------------------------------------------

    def _pad(self, content: Raster, grid: config.GridPlan) -> Raster:
        """Expand a content-only raster to the full grid with letterboxing."""
        content_w = grid.content_cols
        out_chars: list[str] = []
        out_fg: list[Optional[RGB]] = []
        out_bg: Optional[list[Optional[RGB]]] = [] if content.bg is not None else None

        dst = 0
        for r in range(grid.rows):
            in_content = grid.pad_top <= r < grid.pad_top + grid.content_rows
            for c in range(grid.cols):
                if in_content and grid.pad_left <= c < grid.pad_left + content_w:
                    out_chars.append(content.chars[dst])
                    out_fg.append(content.fg[dst])
                    if out_bg is not None:
                        out_bg.append(content.bg[dst])
                    dst += 1
                else:
                    out_chars.append(" ")
                    out_fg.append(None)
                    if out_bg is not None:
                        out_bg.append(None)

        return Raster(chars=out_chars, fg=out_fg, bg=out_bg)

    def _blank_frame(self, grid: config.GridPlan) -> bytes:
        n = grid.cols * grid.rows
        raster = Raster(chars=[" "] * n, fg=[None] * n)
        if self._colored:
            return encode_raster(raster, grid.cols)
        return encode_plain(raster, grid.cols)

    # -- helpers shared by concrete renderers -----------------------------------

    def _luma(self, sized: np.ndarray) -> np.ndarray:
        return lummod.luminance(sized)

    def _to_rgb(self, value: np.ndarray) -> tuple[int, int, int]:
        return (int(value[0]), int(value[1]), int(value[2]))