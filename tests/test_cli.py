"""CLI: argument parsing, validation, exit codes and factory wiring."""

from __future__ import annotations

import pytest

from rgbascii.cli.commands import build_parser, main, make_config
from rgbascii.config import RenderMode, SampleMethod
from rgbascii.errors import ConfigError


def test_parser_requires_video_for_main():
    assert main([]) == 2


def test_help_exits_zero(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "rgbascii" in out
    assert "--mode" in out
    assert "--charset" in out


def test_version_exits_zero(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    assert "rgbascii" in capsys.readouterr().out


def test_invalid_mode_exits_two():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["video.mp4", "--mode", "nonsense"])
    assert exc.value.code == 2


def test_invalid_width_value_main_returns_one():
    assert main(["video.mp4", "--width", "2"]) == 1


def test_missing_video_file_returns_one():
    assert main(["/nonexistent/path/to/video.mp4"]) == 1


def test_make_config_defaults():
    args = build_parser().parse_args(["movie.mp4"])
    cfg = make_config(args)
    assert cfg.mode is RenderMode.ASCII
    assert cfg.sample is SampleMethod.AVERAGE
    assert cfg.loop is True
    assert cfg.no_audio is False


def test_make_config_mode_alias():
    args = build_parser().parse_args(["movie.mp4", "--mode", "rgb"])
    cfg = make_config(args)
    assert cfg.mode is RenderMode.RGB
    assert cfg.mode.renderer_key == "ascii"


def test_make_config_no_color():
    args = build_parser().parse_args(["movie.mp4", "--no-color"])
    cfg = make_config(args)
    assert cfg.color is False


def test_make_config_color_levels_validation():
    args = build_parser().parse_args(["movie.mp4", "--color-levels", "0"])
    with pytest.raises(ConfigError):
        make_config(args)


def test_make_config_mono_color():
    args = build_parser().parse_args(["movie.mp4", "--mode", "mono", "--mono-color", "#ff8800"])
    cfg = make_config(args)
    assert cfg.mono_color == (255, 136, 0)


def test_make_config_bad_mono_color_exits_two():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["movie.mp4", "--mono-color", "zzz"])
    assert exc.value.code == 2


def test_make_config_start_end():
    args = build_parser().parse_args(["movie.mp4", "--start", "30", "--end", "60"])
    cfg = make_config(args)
    assert cfg.start == 30
    assert cfg.end == 60


def test_make_config_end_before_start_invalid():
    args = build_parser().parse_args(["movie.mp4", "--start", "30", "--end", "10"])
    with pytest.raises(ConfigError):
        make_config(args)


def test_custom_charset():
    args = build_parser().parse_args(["movie.mp4", "--charset", " .#"])
    cfg = make_config(args)
    assert cfg.resolve_charset() == " .#"