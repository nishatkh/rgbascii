"""Render one frame of a video to standalone ANSI art (no live playback).

Useful for capturing a still as text, or verifying a renderer on a headless
machine: the compact escape encoder minimises the byte size of the dump.

Usage:
    python examples/render_still.py <video> [--width 80] [--mode halfblock]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rgbascii.config import Config, RenderMode
from rgbascii.processing import luminance as lummod
from rgbascii.processing import resize as resizemod
from rgbascii.rendering import build_renderer
from rgbascii.rendering.ansi import encode
from rgbascii.video.ffmpeg import FFmpegVideoDecoder


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video")
    ap.add_argument("--width", type=int, default=80)
    ap.add_argument("--mode", choices=[m.value for m in RenderMode], default=RenderMode.ASCII.value)
    ap.add_argument("--seek", type=float, default=1.0, help="second to grab")
    ap.add_argument("--color", action="store_true")
    args = ap.parse_args()

    dec = FFmpegVideoDecoder(args.video, target_fps=None, queue_size=8)
    idx, frame = None, None
    target = int(args.seek * dec.metadata().fps)
    for idx, frame in dec.frames(end=args.seek + 1.0):
        if idx >= target:
            break
    dec.stop()
    if frame is None:
        print("could not decode a frame", file=sys.stderr)
        return 1

    cfg = Config(
        input_file=args.video,
        mode=RenderMode.from_name(args.mode),
        width=args.width,
        color=args.color or True,
    )
    cfg.source_width, cfg.source_height = dec.work_width, dec.work_height
    import os
    try:
        size = os.get_terminal_size()
    except OSError:
        size = os.terminal_size((80, 24))
    grid = cfg.compute_grid(size.columns, size.lines)

    renderer = build_renderer(cfg)
    content = renderer._compose(
        renderer._adjuster.apply(resizemod.resize(frame, grid.content_cols, grid.content_rows * renderer.CELL_H, method="average")),
        grid.content_cols,
    )
    blob = encode(content, grid.content_cols).rstrip(b"\n")
    sys.stdout.buffer.write(blob)
    sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())