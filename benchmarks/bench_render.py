"""Pipeline micro-benchmarks.

Runs the full render pipeline (resize -> adjust -> luma -> LUT -> colours ->
ANSI encode -> bytes) over synthetic frames at several grid sizes and modes,
and reports per-stage timings.  Run with:

    python benchmarks/bench_render.py            # included grids/modes
    python benchmarks/bench_render.py 200 60     # custom grid

The numbers are advisory: on a 120x40 full-colour grid the whole frame
should render in single-digit milliseconds on any modern machine.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rgbascii.config import Config, GridPlan, RenderMode
from rgbascii.processing import color as colmod
from rgbascii.processing import luminance as lummod
from rgbascii.processing import resize as resizemod
from rgbascii.rendering import build_renderer
from rgbascii.rendering.ansi import encode as encode_ansi
from rgbascii.rendering.ansi import Raster

GRIDS = [(80, 24), (120, 40), (160, 50), (240, 80)]
MODES = [RenderMode.GRAYSCALE, RenderMode.ASCII, RenderMode.HALFBLOCK]
FRAMES = 30


def _times(stage_fn, iters=200):
    best = 1e9
    for _ in range(iters):
        t0 = time.perf_counter()
        stage_fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1000  # ms


def make_frame(cols, rows):
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, (rows * 3, cols * 3, 3), dtype=np.uint8)


def main() -> None:
    grids = GRIDS
    if len(sys.argv) >= 3:
        grids = [(int(sys.argv[1]), int(sys.argv[2]))]

    print(f"{'grid':<12}{'mode':<12}{'resize':>8}{'color':>8}{'luma':>8}"
          f"{'enc':>8}{'total':>8}{'fps':>8}")
    print("-" * 72)

    for cols, rows in grids:
        frame = make_frame(cols, rows)
        for mode in MODES:
            cfg = Config(input_file="", mode=mode, width=cols, height=rows,
                         color=True, color_levels=None)
            cfg.source_width, cfg.source_height = frame.shape[1], frame.shape[0]
            grid = cfg.compute_grid(cols + 40, rows + 20)
            renderer = build_renderer(cfg)

            sample_w = grid.content_cols
            sample_h = grid.content_rows * renderer.CELL_H

            def resize_pass():
                return resizemod.resize(frame, sample_w, sample_h, method="average")

            def color_pass():
                return renderer._adjuster.apply(resize_pass())

            def luma_pass():
                return lummod.luminance(color_pass())

            def full_pass():
                return renderer.render(frame, grid)

            t_resize = _times(resize_pass)
            t_color = _times(color_pass)
            t_luma = _times(luma_pass)
            t_total = _times(full_pass)
            blob_len = len(full_pass())
            t_enc = max(0.0, t_total - t_color - t_color * 0.1)
            fps = 1000.0 / t_total if t_total > 0 else 0
            print(f"{grid.content_cols}x{grid.content_rows:<9}"
                  f"{mode.value:<12}{t_resize:>8.3f}{t_color:>8.3f}{t_luma:>8.3f}"
                  f"{t_enc:>8.3f}{t_total:>8.3f}{fps:>7.1f}  ({blob_len} B/frame)")


if __name__ == "__main__":
    main()