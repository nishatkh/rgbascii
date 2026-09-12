"""Frame-level ANSI encoder.

Optimizations, in priority order:

* one ``\\x1b[H`` + one ``\\x1b[0m`` per frame, not per row;
* colours are only emitted when they *change* (state is carried across rows,
  because terminal colour state survives newlines);
* ``None`` cells (letterbox padding) fall back to the terminal's default
  foreground/background via cheap ``39m``/``49m`` rather than a full reset;
* every row ends with ``\\x1b[K`` so stale content from a previously wider
  frame is erased without ever scrolling;
* the caller pre-computes flat Python lists, so the hot loop is a tight zip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from ..terminal import ansi as term

RGB = tuple[int, int, int]


@dataclass
class Raster:
    """Flat cell data for one rendered frame (length = cols * rows)."""

    chars: list[str]
    fg: list[Optional[RGB]]
    bg: Optional[list[Optional[RGB]]] = None

    @property
    def is_empty(self) -> bool:
        return not self.chars

    def cells(self) -> Iterator[tuple[str, Optional[RGB], Optional[RGB]]]:
        if self.bg is None:
            for ch, f in zip(self.chars, self.fg):
                yield ch, f, None
        else:
            for ch, f, b in zip(self.chars, self.fg, self.bg):
                yield ch, f, b


def encode(raster: Raster, cols: int) -> bytes:
    """Convert a raster to a single ANSI byte string for one frame."""
    if not raster.chars:
        return b""

    out: list[str] = []
    use_bg = raster.bg is not None
    last_fg: Optional[RGB] = None
    last_bg: Optional[RGB] = None

    out.append(term.HOME)
    out.append(term.RESET)

    for i, (ch, f, b) in enumerate(raster.cells()):
        if i and i % cols == 0:
            out.append(term.ERASE_LINE)
            out.append("\n")

        if use_bg:
            last_fg = _update_fg(out, f, last_fg)
            last_bg = _update_bg(out, b, last_bg)
        else:
            last_fg = _update_fg(out, f, last_fg)
        out.append(ch)

    out.append(term.ERASE_LINE)
    return "".join(out).encode("utf-8", "replace")


def _update_fg(seq: list[str], f: Optional[RGB], last: Optional[RGB]) -> Optional[RGB]:
    if f is None:
        if last is not None:
            seq.append(term.DEFAULT_FG)
        return None
    if f != last:
        seq.append(term.fg(*f))
    return f


def _update_bg(seq: list[str], b: Optional[RGB], last: Optional[RGB]) -> Optional[RGB]:
    if b is None:
        if last is not None:
            seq.append(term.DEFAULT_BG)
        return None
    if b != last:
        seq.append(term.bg(*b))
    return b


def plain(raster: Raster, cols: int) -> bytes:
    """No-colour rendering: home cursor each frame, text rows, no SGR codes."""
    if not raster.chars:
        return b""
    out: list[str] = [term.HOME]
    for i, (ch, _f, _b) in enumerate(raster.cells()):
        if i and i % cols == 0:
            out.append(term.ERASE_LINE)
            out.append("\n")
        out.append(ch)
    out.append(term.ERASE_LINE)
    return "".join(out).encode("utf-8", "replace")