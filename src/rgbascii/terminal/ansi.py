"""Low-level ANSI escape sequence builders.

Only small, deterministic helpers live here; the frame-level encoder that
optimizes color transitions lives in ``rendering.ansi`` and the terminal
screen management lives in ``terminal.renderer``.
"""

from __future__ import annotations

ESC = "\x1b"

# Cursor / screen control
HOME = f"{ESC}[H"            # move cursor to 1;1
CLEAR = f"{ESC}[2J"          # clear whole screen
ERASE_LINE = f"{ESC}[K"      # clear from cursor to end of line
UP = f"{ESC}[1A"             # cursor up one line
HIDE_CURSOR = f"{ESC}[?25l"
SHOW_CURSOR = f"{ESC}[?25h"
ALT_SCREEN_ON = f"{ESC}[?1049h"
ALT_SCREEN_OFF = f"{ESC}[?1049l"
RESET = f"{ESC}[0m"
BRIGHT = f"{ESC}[1m"
DIM = f"{ESC}[2m"

# Colors
DEFAULT_FG = f"{ESC}[39m"
DEFAULT_BG = f"{ESC}[49m"


def fg(r: int, g: int, b: int) -> str:
    return f"{ESC}[38;2;{r};{g};{b}m"


def bg(r: int, g: int, b: int) -> str:
    return f"{ESC}[48;2;{r};{g};{b}m"


def cursor_to(col: int, row: int) -> str:
    return f"{ESC}[{row};{col}H"


def sgr(*codes: int) -> str:
    return f"{ESC}[{';'.join(str(c) for c in codes)}m"