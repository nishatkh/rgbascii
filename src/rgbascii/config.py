"""Application configuration.

A single ``Config`` dataclass carries every tunable.  It is built by the CLI
parser, validated, and then passed (largely read-only) through the whole
pipeline.  Derived values such as the rendered grid are computed here so the
renderers and player never re-derive policy.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .errors import ConfigError

# ---------------------------------------------------------------------------
# Types / enums
# ---------------------------------------------------------------------------


class RenderMode(str, Enum):
    ASCII = "ascii"
    RGB = "rgb"  # alias of ascii, kept for readability
    GRAYSCALE = "grayscale"
    MONO = "mono"
    HALFBLOCK = "halfblock"

    @classmethod
    def from_name(cls, value: str) -> "RenderMode":
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(m.value for m in cls)
            raise ConfigError(f"unknown mode {value!r} (choose from: {valid})") from None

    @property
    def renderer_key(self) -> str:
        return "ascii" if self is RenderMode.RGB else self.value


class SampleMethod(str, Enum):
    CENTER = "center"
    AVERAGE = "average"
    WEIGHTED = "weighted"

    @classmethod
    def from_name(cls, value: str) -> "SampleMethod":
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(m.value for m in cls)
            raise ConfigError(f"unknown sample method {value!r} (choose from: {valid})") from None


class ClockSource(str, Enum):
    AUTO = "auto"
    AUDIO = "audio"
    VIDEO = "video"

    @classmethod
    def from_name(cls, value: str) -> "ClockSource":
        try:
            return cls(value.lower())
        except ValueError:
            raise ConfigError(f"unknown clock source {value!r} (choose from auto, audio, video)") from None


# ---------------------------------------------------------------------------
# Character sets
# ---------------------------------------------------------------------------

CHARSET_STANDARD = " .:-=+*#%@"
CHARSET_DENSE = " .`^,:;Il!i~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
CHARSET_MINIMAL = " .#"
CHARSET_BLOCKS = " ░▒▓█"

CHARSETS: dict[str, str] = {
    "standard": CHARSET_STANDARD,
    "dense": CHARSET_DENSE,
    "minimal": CHARSET_MINIMAL,
    "blocks": CHARSET_BLOCKS,
}

ASPECT_DEFAULT = 0.5  # default `--aspect`: classic terminal char correction


# ---------------------------------------------------------------------------
# Grid plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GridPlan:
    """Exact output raster in terminal cells plus letterbox padding."""

    cols: int              # total cells per line
    rows: int              # total lines
    content_cols: int      # cells actually covered by the video
    content_rows: int      # lines actually covered by the video
    pad_left: int
    pad_top: int

    @property
    def is_letterboxed(self) -> bool:
        return self.content_cols < self.cols or self.content_rows < self.rows


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class Config:
    # --- video source ------------------------------------------------------
    input_file: str
    width: Optional[int] = None                  # exact grid width override
    height: Optional[int] = None                 # exact grid height override
    fps: Optional[float] = None                  # target render/decode fps
    loop: bool = False
    start: float = 0.0
    end: Optional[float] = None

    # --- rendering ---------------------------------------------------------
    mode: RenderMode = RenderMode.ASCII
    charset: str = CHARSET_STANDARD
    invert: bool = False
    aspect: float = ASPECT_DEFAULT               # vertical shrink factor
    sample: SampleMethod = SampleMethod.AVERAGE
    color_levels: Optional[int] = None           # color quantization

    # --- image adjustment ---------------------------------------------------
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0

    # --- color policy --------------------------------------------------------
    color: Optional[bool] = None                 # None = auto (tty + NO_COLOR)
    mono_color: tuple[int, int, int] = (255, 255, 255)

    # --- playback -------------------------------------------------------------
    clock: ClockSource = ClockSource.AUTO
    buffer_ms: int = 120                         # decode-ahead queue budget
    catchup_ms: int = 350                        # lag that triggers a hard reseek
    no_audio: bool = False

    # --- terminal -------------------------------------------------------------
    fullscreen: bool = True                    # use alternate screen buffer
    debug: bool = False
    frames: Optional[int] = None                 # render at most N frames

    # runtime values filled by the engine (never parsed from the CLI)
    source_width: int = 0
    source_height: int = 0

    # --- color ---------------------------------------------------------------

    @property
    def color_enabled(self) -> bool:
        if self.color is not None:
            return self.color
        if os.environ.get("NO_COLOR"):
            return False
        return bool(sys.stdout.isatty())

    # --- validation -------------------------------------------------------------

    def validate(self) -> None:
        if not self.input_file:
            raise ConfigError("no input video specified")
        if self.width is not None and self.width < 8:
            raise ConfigError("--width must be >= 8")
        if self.height is not None and self.height < 4:
            raise ConfigError("--height must be >= 4")
        if self.fps is not None and not (1 <= self.fps <= 240):
            raise ConfigError("--fps must be between 1 and 240")
        if not (0.01 <= self.aspect <= 8.0):
            raise ConfigError("--aspect must be between 0.01 and 8.0")
        if self.start < 0:
            raise ConfigError("--start cannot be negative")
        if self.end is not None and self.end <= self.start:
            raise ConfigError("--end must be greater than --start")
        if self.color_levels is not None and not (1 <= self.color_levels <= 256):
            raise ConfigError("--color-levels must be between 1 and 256")
        self.resolve_charset()
        if not (32 <= self.buffer_ms <= 2000):
            raise ConfigError("--buffer-ms must be between 32 and 2000")
        if not (32 <= self.catchup_ms <= 5000):
            raise ConfigError("--catchup-ms must be between 32 and 5000")

    def resolve_charset(self) -> str:
        value = self.charset
        if value in CHARSETS:
            value = CHARSETS[value]
        if not value:
            raise ConfigError("charset must not be empty")
        if len(value) > 0 and any(ord(ch) < 32 or ch == "\x7f" for ch in value):
            raise ConfigError("charset contains control characters")
        return value

    # --- grid computation -----------------------------------------------------

    def natural_row_ratio(self) -> float:
        """How many terminal rows one video row needs to look natural."""
        w, h = self.source_width, self.source_height
        if w <= 0 or h <= 0:
            return self.aspect
        return (h / w) * self.aspect

    def compute_grid(self, term_cols: int, term_rows: int) -> GridPlan:
        """Map source aspect onto the terminal cell grid.

        * if both width and height are set, use them exactly and letterbox
          the image inside that box;
        * otherwise derive the missing dimension from the aspect correction;
        * never exceed the live terminal dimensions.
        """
        ratio = self.natural_row_ratio()

        cols: int
        rows: int

        if self.width is not None and self.height is not None:
            cols, rows = self.width, self.height
        elif self.width is not None:
            cols = self.width
            rows = round(cols * ratio)
        elif self.height is not None:
            rows = self.height
            cols = round(rows / ratio) if ratio > 0 else self.height
        else:
            cols = term_cols
            rows = round(cols * ratio)

        # clamp into the terminal so we never write beyond its borders
        if cols > term_cols:
            cols = term_cols
            rows = round(cols * ratio)
        if rows > term_rows:
            rows = term_rows
            cols = round(rows / ratio) if ratio > 0 else term_rows
        if cols > term_cols:
            cols = term_cols
            rows = term_rows

        cols = max(1, cols)
        rows = max(1, rows)

        content_cols = cols
        content_rows = rows
        if self.width is not None and self.height is not None:
            # letterbox inside the requested box
            fit_rows = round(cols * ratio)
            if fit_rows <= rows:
                content_rows = fit_rows
            else:
                content_cols = round(rows / ratio) if ratio > 0 else cols
                content_rows = rows
        else:
            # shrink to full grid only when the derived size exceeds the terminal
            content_cols = min(cols, term_cols)
            content_rows = min(rows, term_rows)

        pad_left = max(0, (cols - content_cols) // 2)
        pad_top = max(0, (rows - content_rows) // 2)
        return GridPlan(cols, rows, content_cols, content_rows, pad_left, pad_top)