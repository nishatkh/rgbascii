"""The `rgbascii` command-line interface.

Parses and validates options, wires Config + decoder + renderer + terminal +
player together, and translates every failure into a single concise message
(with exit codes: 0 = success, 1 = runtime error, 2 = usage error).
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from .. import __version__
from ..config import (
    ASPECT_DEFAULT,
    CHARSET_STANDARD,
    CHARSETS,
    ClockSource,
    Config,
    RenderMode,
    SampleMethod,
)
from ..errors import RgbasciiError
from ..rendering import build_renderer
from ..terminal.renderer import TerminalScreen
from ..video.ffmpeg import FFmpegVideoDecoder, probe_metadata

CHARSET_HELP = "character ramp (a named preset or a literal string). Presets: " + ", ".join(
    f"{k}={v!r}" for k, v in CHARSETS.items()
).replace("%", "%%")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rgbascii",
        description="Render a video in real time as full-colour RGB ASCII art in the terminal.",
        epilog=(
            "controls: space/p pause   q quit   left/right seek +/- 5s   "
            "+/- resolution   r reset   resize adapts automatically"
        ),
    )
    parser.add_argument("video", nargs="?", help="path to the video file")
    parser.add_argument("--version", action="version", version=f"rgbascii {__version__}")

    g = parser.add_argument_group("terminal size")
    g.add_argument("--width", type=int, default=None, metavar="N", help="render width in cells")
    g.add_argument("--height", type=int, default=None, metavar="N", help="render height in cells")
    g.add_argument("--fullscreen", dest="fullscreen", action="store_true", default=None, help="use the alternate screen buffer (default)")
    g.add_argument("--no-fullscreen", dest="fullscreen", action="store_false", help="render in place without the alternate screen buffer")

    g = parser.add_argument_group("rendering")
    g.add_argument(
        "--mode",
        type=str,
        default=RenderMode.ASCII.value,
        choices=[m.value for m in RenderMode],
        help="renderer: ascii|rgb|grayscale|mono|halfblock (default: ascii)",
    )
    g.add_argument("--charset", type=str, default=CHARSET_STANDARD, metavar="STR", help=CHARSET_HELP)
    g.add_argument("--invert", action="store_true", help="swap the luminance->character mapping")
    g.add_argument("--aspect", type=float, default=ASPECT_DEFAULT, metavar="F", help="vertical aspect correction (default: %(default)s)")
    g.add_argument(
        "--sample",
        type=str,
        default=SampleMethod.AVERAGE.value,
        choices=[m.value for m in SampleMethod],
        help="per-cell colour sampling: average|center|weighted (default: average)",
    )
    g.add_argument("--color-levels", type=int, default=None, metavar="N", help="quantize colors to N levels per channel (1-256)")
    g.add_argument("--mono-color", type=_parse_color, default=None, metavar="RRGGBB", help="fixed color for --mode mono")

    g = parser.add_argument_group("image adjustment")
    g.add_argument("--brightness", type=float, default=0.0, metavar="F", help="additive brightness (-1..1, default 0)")
    g.add_argument("--contrast", type=float, default=1.0, metavar="F", help="multiplicative contrast (default 1)")
    g.add_argument("--saturation", type=float, default=1.0, metavar="F", help="saturation factor (default 1)")
    g.add_argument("--gamma", type=float, default=1.0, metavar="F", help="gamma correction (default 1)")

    g = parser.add_argument_group("color")
    g.add_argument("--color", dest="color", action="store_true", default=None, help="force ANSI color on")
    g.add_argument("--no-color", dest="color", action="store_false", help="render without any color escape codes")

    g = parser.add_argument_group("playback")
    g.add_argument("--fps", type=float, default=None, metavar="N", help="target playback fps (decode rate)")
    g.add_argument("--loop", dest="loop", action="store_true", default=True, help="loop the video forever (default: on)")
    g.add_argument("--no-loop", dest="loop", action="store_false", help="stop after the video ends instead of looping")
    g.add_argument("--start", type=float, default=0.0, metavar="S", help="start offset in seconds")
    g.add_argument("--end", type=float, default=None, metavar="E", help="stop offset in seconds")
    g.add_argument("--clock", type=str, default=ClockSource.AUTO.value, choices=[c.value for c in ClockSource], help="master clock: auto|audio|video")
    g.add_argument("--buffer-ms", type=int, default=120, metavar="MS", help="decode-ahead queue budget in ms")
    g.add_argument("--catchup-ms", type=int, default=350, metavar="MS", help="lag that triggers a hard decode reseek")
    g.add_argument("--no-audio", action="store_true", help="disable audio entirely")

    g = parser.add_argument_group("misc")
    g.add_argument("--debug", action="store_true", help="print statistics to stderr")
    g.add_argument("--frames", type=int, default=None, metavar="N", help="render at most N frames then exit")
    return parser


def _parse_color(value: str) -> tuple[int, int, int]:
    stripped = value.strip().lstrip("#")
    if len(stripped) != 6:
        raise argparse.ArgumentTypeError("color must be RRGGBB hex")
    try:
        return (int(stripped[0:2], 16), int(stripped[2:4], 16), int(stripped[4:6], 16))
    except ValueError:
        raise argparse.ArgumentTypeError("color must be RRGGBB hex") from None


def make_config(args: argparse.Namespace) -> Config:
    cfg = Config(input_file=args.video or "")
    cfg.width = args.width
    cfg.height = args.height
    cfg.fps = args.fps
    cfg.loop = args.loop
    cfg.start = args.start
    cfg.end = args.end
    cfg.mode = RenderMode.from_name(args.mode)
    cfg.charset = args.charset
    cfg.invert = args.invert
    cfg.aspect = args.aspect
    cfg.sample = SampleMethod.from_name(args.sample)
    cfg.color_levels = args.color_levels
    cfg.brightness = args.brightness
    cfg.contrast = args.contrast
    cfg.saturation = args.saturation
    cfg.gamma = args.gamma
    cfg.color = args.color
    cfg.clock = ClockSource.from_name(args.clock)
    cfg.buffer_ms = args.buffer_ms
    cfg.catchup_ms = args.catchup_ms
    cfg.no_audio = args.no_audio
    if args.fullscreen is not None:
        cfg.fullscreen = args.fullscreen
    cfg.debug = args.debug
    cfg.frames = args.frames
    if args.mono_color is not None:
        cfg.mono_color = args.mono_color
    cfg.validate()
    return cfg


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.video:
        parser.print_usage(sys.stderr)
        print("rgbascii: error: the following arguments are required: VIDEO", file=sys.stderr)
        return 2

    cfg: Optional[Config] = None
    try:
        cfg = make_config(args)
        meta = probe_metadata(cfg.input_file)
        queue_size = max(4, int(cfg.buffer_ms / 1000 * (cfg.fps or meta.fps)))
        decoder = FFmpegVideoDecoder(cfg.input_file, cfg.fps, queue_size=queue_size)
        cfg.source_width = meta.width
        cfg.source_height = meta.height

        renderer = build_renderer(cfg)

        use_fullscreen = cfg.fullscreen and sys.stdout.isatty()
        with TerminalScreen(fullscreen=use_fullscreen, use_raw_input=sys.stdin.isatty()) as screen:
            from ..playback.player import PlaybackEngine

            engine = PlaybackEngine(cfg, meta, decoder, renderer, screen)
            return engine.run()
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    except RgbasciiError as exc:
        print(f"rgbascii: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - safety net
        print(f"rgbascii: unexpected error: {exc}", file=sys.stderr)
        if cfg is not None and cfg.debug:  # pragma: no cover
            raise
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())