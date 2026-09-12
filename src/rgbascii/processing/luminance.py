"""Perceptual luminance.

Uses the Rec. 709 luma coefficients rather than a naive ``(R+G+B)/3``.
The optional naive formula is offered as a contrast with the documented best
practice; the default is perceptual.
"""

from __future__ import annotations

import numpy as np

LUMA_REC709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
LUMA_NAIVE = np.array([1.0 / 3.0] * 3, dtype=np.float32)


def luminance(rgb: np.ndarray, naive: bool = False) -> np.ndarray:
    """Return uint8 luma for an ``(..., 3)`` uint8 RGB array."""
    coef = LUMA_NAIVE if naive else LUMA_REC709
    out = rgb.astype(np.float32, copy=False).dot(coef)
    return np.clip(out, 0, 255).astype(np.uint8)


def luminance_float(rgb: np.ndarray, naive: bool = False) -> np.ndarray:
    """Return float32 luma in ``[0, 1]`` for an ``(..., 3)`` uint8 array."""
    coef = LUMA_NAIVE if naive else LUMA_REC709
    return np.clip(rgb.astype(np.float32, copy=False).dot(coef) / 255.0, 0.0, 1.0)