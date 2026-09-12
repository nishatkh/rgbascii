"""Config: validation and grid/aspect computation."""

from __future__ import annotations

import pytest

from rgbascii.config import ASPECT_DEFAULT, Config, RenderMode, SampleMethod
from rgbascii.errors import ConfigError


def make(**kw) -> Config:
    cfg = Config(input_file="movie.mp4", **kw)
    cfg.source_width = 1920
    cfg.source_height = 1080
    return cfg


def test_default_grid_is_terminal_width():
    grid = make().compute_grid(120, 40)
    assert grid.cols == 120
    # 16:9 -> 120 * (1080/1920) * 0.5 = 33.75 -> 34 rows
    assert grid.content_rows == round(120 * (1080 / 1920) * ASPECT_DEFAULT)


def test_grid_never_exceeds_terminal():
    grid = make(width=500, height=500).compute_grid(120, 40)
    assert grid.cols <= 120
    assert grid.rows <= 40


def test_only_width_derives_height():
    grid = make(width=100).compute_grid(200, 100)
    assert grid.cols == 100
    assert grid.content_rows == round(100 * (1080 / 1920) * ASPECT_DEFAULT)


def test_only_height_derives_width():
    grid = make(height=20).compute_grid(200, 100)
    assert grid.rows <= 100
    assert grid.content_rows == 20


def test_both_dimensions_letterbox():
    # A very short box for a tall video should letterbox horizontally
    cfg = make(width=100, height=10)
    cfg.source_width, cfg.source_height = 1080, 1920  # portrait
    grid = cfg.compute_grid(200, 100)
    assert grid.cols == 100
    assert grid.rows == 10
    assert grid.content_rows == 10
    assert grid.content_cols <= 100
    assert grid.pad_left >= 0


def test_aspect_changes_rows():
    narrow = make(aspect=0.25).compute_grid(120, 200).content_rows
    wide = make(aspect=1.0).compute_grid(120, 200).content_rows
    assert wide > narrow


def test_validate_rejects_bad_width():
    with pytest.raises(ConfigError):
        make(width=2).validate()


def test_validate_rejects_bad_fps():
    with pytest.raises(ConfigError):
        make(fps=0).validate()
    with pytest.raises(ConfigError):
        make(fps=500).validate()


def test_validate_rejects_bad_end():
    with pytest.raises(ConfigError):
        make(start=10, end=5).validate()


def test_validate_rejects_empty_charset():
    with pytest.raises(ConfigError):
        make(charset="").validate()


def test_validate_rejects_control_chars():
    with pytest.raises(ConfigError):
        make(charset="a\nb").validate()


def test_charset_presets_resolve():
    cfg = make(charset="dense")
    assert cfg.resolve_charset() == __import__("rgbascii.config", fromlist=["CHARSET_DENSE"]).CHARSET_DENSE


def test_custom_charset_passthrough():
    cfg = make(charset=" .#")
    assert cfg.resolve_charset() == " .#"


def test_mode_from_name():
    assert RenderMode.from_name("HALFBLOCK") is RenderMode.HALFBLOCK
    assert RenderMode.from_name("rgb").renderer_key == "ascii"
    with pytest.raises(ConfigError):
        RenderMode.from_name("nope")


def test_sample_from_name():
    assert SampleMethod.from_name("CENTER") is SampleMethod.CENTER
    with pytest.raises(ConfigError):
        SampleMethod.from_name("nope")