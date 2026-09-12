"""Renderer pipeline: ASCII, grayscale, mono, half-block end-to-end."""

from __future__ import annotations

import numpy as np
import pytest

from rgbascii.config import CHARSET_STANDARD, Config, RenderMode
from rgbascii.rendering import build_renderer
from rgbascii.terminal import ansi as term

from conftest import gradient, solid


def make(mode: RenderMode = RenderMode.ASCII, **kw) -> Config:
    kw.setdefault("width", 24)
    cfg = Config(input_file="movie.mp4", mode=mode, color=True, **kw)
    cfg.source_width, cfg.source_height = 1920, 1080
    return cfg


def cells_for(renderer, frame, grid):
    """Render and split the ANSI blob into an (rows, cols, fg, bg) structure
    by calling the internal compose/pad steps (deterministic, terminal-free)."""
    sample_h = grid.content_rows * renderer.CELL_H
    from rgbascii.processing.resize import resize

    sized = resize(frame, grid.content_cols, sample_h, method="average")
    sized = renderer._adjuster.apply(sized)
    content = renderer._compose(sized, grid.content_cols)
    return renderer._pad(content, grid)


# ---------------------------------------------------------------------------
# ascii
# ---------------------------------------------------------------------------


def test_ascii_frame_size():
    cfg = make()
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    blob = r.render(gradient(), grid)
    assert blob.startswith(term.HOME.encode())
    assert blob.count(b"\n") == grid.rows - 1


def test_white_frame_is_heavy_glyph():
    cfg = make()
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    cells = cells_for(r, solid((255, 255, 255)), grid)
    assert cells.chars[0] == CHARSET_STANDARD[-1]


def test_black_frame_is_space_glyph():
    cfg = make()
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    cells = cells_for(r, solid((0, 0, 0)), grid)
    assert cells.chars[0] == " "


def test_red_frame_keeps_red_foreground():
    cfg = make()
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    cells = cells_for(r, solid((255, 0, 0)), grid)
    assert cells.fg[0] == (255, 0, 0)
    assert cells.bg is None or all(b is None for b in cells.bg)


def test_gradient_monotonic_characters():
    cfg = make()
    r = build_renderer(cfg)
    grid = cfg.compute_grid(200, 100)
    cells = cells_for(r, gradient(64, 256), grid)
    order = {ch: i for i, ch in enumerate(CHARSET_STANDARD)}
    row = [order[ch] for ch in cells.chars[: grid.content_cols]]
    assert row == sorted(row)


def test_invert_swaps_glyphs():
    normal = build_renderer(make())
    inverted = build_renderer(make(invert=True))
    grid = normal.cfg.compute_grid(80, 24)
    a = cells_for(normal, solid((255, 255, 255)), grid)
    b = cells_for(inverted, solid((255, 255, 255)), grid)
    assert a.chars[0] != b.chars[0]


def test_no_color_emits_no_sgr():
    cfg = make()
    cfg.color = False
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    blob = r.render(solid((255, 0, 0)), grid)
    assert b"38;2;" not in blob


# ---------------------------------------------------------------------------
# padding
# ---------------------------------------------------------------------------


def test_letterbox_padding_is_spaces():
    cfg = make(width=20, height=20)
    cfg.source_width, cfg.source_height = 1080, 1920  # portrait -> horizontal bars
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    cells = cells_for(r, solid((255, 0, 0)), grid)
    assert len(cells.chars) == grid.cols * grid.rows
    assert cells.fg[0] is None  # top-left is letterbox
    assert grid.is_letterboxed


# ---------------------------------------------------------------------------
# grayscale
# ---------------------------------------------------------------------------


def test_grayscale_colors_are_neutral():
    cfg = make(RenderMode.GRAYSCALE)
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    cells = cells_for(r, solid((255, 0, 0)), grid)
    r0, g0, b0 = cells.fg[0]
    assert r0 == g0 == b0


# ---------------------------------------------------------------------------
# mono
# ---------------------------------------------------------------------------


def test_mono_uses_fixed_color():
    cfg = make(RenderMode.MONO)
    cfg.mono_color = (0, 255, 128)
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    cells = cells_for(r, gradient(), grid)
    assert all(c == (0, 255, 128) for c in cells.fg if c is not None)


# ---------------------------------------------------------------------------
# half-block
# ---------------------------------------------------------------------------


def test_halfblock_samples_two_rows_per_cell():
    cfg = make(RenderMode.HALFBLOCK)
    r = build_renderer(cfg)
    # alternating rows: each cell (top,bottom) = (white, black)
    sample = np.zeros((4, 3, 3), dtype=np.uint8)
    sample[0] = 255
    sample[2] = 255
    content = r._compose(sample, content_cols=3)
    assert content.chars[0] == "\u2580"
    assert content.fg[0] == (255, 255, 255)
    assert content.bg[0] == (0, 0, 0)
    assert content.chars[1] == "\u2580"


def test_halfblock_equal_colors_collapse_to_space():
    cfg = make(RenderMode.HALFBLOCK)
    r = build_renderer(cfg)
    sample = np.full((4, 3, 3), (10, 20, 30), dtype=np.uint8)
    content = r._compose(sample, content_cols=3)
    assert content.chars[0] == " "
    assert content.bg[0] == (10, 20, 30)
    assert content.fg[0] is None


def test_halfblock_encodes_background():
    cfg = make(RenderMode.HALFBLOCK)
    r = build_renderer(cfg)
    # each cell is two-tone: (top=red, bottom=blue) for both cells
    sample = np.zeros((4, 3, 3), dtype=np.uint8)
    sample[0] = (255, 0, 0)
    sample[1] = (0, 0, 255)
    sample[2] = (255, 0, 0)
    sample[3] = (0, 0, 255)
    content = r._compose(sample, content_cols=3)
    from rgbascii.rendering.ansi import encode

    blob = encode(content, cols=3)
    assert b"\x1b[38;2;255;0;0m" in blob
    assert b"\x1b[48;2;0;0;255m" in blob


# ---------------------------------------------------------------------------
# quantization / adjustments through the pipeline
# ---------------------------------------------------------------------------


def test_color_levels_reduce_distinct_colors():
    plain = build_renderer(make())
    quant = build_renderer(make(color_levels=2))
    grid = plain.cfg.compute_grid(80, 24)
    a = cells_for(plain, gradient(64, 256), grid)
    b = cells_for(quant, gradient(64, 256), grid)
    assert len(set(a.fg)) > len(set(b.fg))


def test_brightness_pipeline_runs():
    cfg = make(brightness=0.4)
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    blob = r.render(solid((50, 50, 50)), grid)
    assert blob


@pytest.mark.parametrize("mode", list(RenderMode))
def test_every_mode_renders(mode):
    cfg = make(mode)
    r = build_renderer(cfg)
    grid = cfg.compute_grid(80, 24)
    assert r.render(gradient(), grid)