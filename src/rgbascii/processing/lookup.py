"""Luminance -> ASCII character lookup tables.

Building a 256-entry table once and indexing it is radically faster than
recomputing a ``luminance * len(charset)`` index for every cell in Python.
The table stores the *string* for every possible luma value, so character
selection is a single LUT lookup per cell.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def build_char_tables(charset: str, invert: bool = False) -> tuple[list[str], np.ndarray]:
    """Build rendering tables for a character set.

    Returns ``(char_list, lut)`` where ``char_list[i]`` is the glyph for LUT
    value ``i`` and ``lut[luma]`` gives the table index for a luma byte.
    """
    chars = list(charset)
    n = len(chars)
    if n == 1:
        return chars, np.zeros(256, dtype=np.uint8)

    cnt = np.arange(256, dtype=np.float32) * (n - 1) / 255.0
    idx = np.clip(np.round(cnt), 0, n - 1).astype(np.uint8)
    if invert:
        idx = n - 1 - idx
    return chars, idx


def char_for_luma(luma: int, char_list: Sequence[str], lut: np.ndarray) -> str:
    """Single-cell helper (used by tests and small paths)."""
    return char_list[int(lut[np.clip(luma, 0, 255)])]