"""Color math: quantization and image adjustments.

All transforms are either precomputed 256-entry lookup tables or single
vectorized passes.  Adjustment flags are checked first so that the default
pipeline (no adjustments, no quantization) costs almost nothing.
"""

from __future__ import annotations

import numpy as np

from .luminance import luminance_float


# ---------------------------------------------------------------------------
# Quantization
# ---------------------------------------------------------------------------


def make_quant_lut(levels: int | None) -> np.ndarray:
    """Return a ``(256,)`` uint8 table mapping any channel value to a level.

    ``levels=None`` (or >= 256) yields the identity table.
    """
    if levels is None or levels >= 256:
        return np.arange(256, dtype=np.uint8)
    steps = levels - 1
    idx = np.clip(np.round(np.arange(256) * steps / 255.0), 0, steps)  # type: ignore[arg-type]
    return (idx * (255.0 / steps)).astype(np.uint8)


def make_color_lut(levels: int | None, brightness: float, contrast: float, gamma: float) -> np.ndarray:
    """Composite per-channel LUT: gamma -> contrast+brightness -> quantize."""
    v = np.arange(256, dtype=np.float32) / 255.0
    if gamma != 1.0:
        v = np.power(np.clip(v, 0.0, 1.0), 1.0 / gamma)
    v = (v - 0.5) * contrast + 0.5 + brightness
    v = np.clip(v, 0.0, 1.0) * 255.0
    lut = np.clip(v, 0, 255).astype(np.uint8)
    if levels is not None and 0 < levels < 256:
        idx = np.clip(np.round(lut.astype(np.float32) * (levels - 1) / 255.0), 0, levels - 1)
        lut = (idx * (255.0 / (levels - 1))).astype(np.uint8)
    return lut


class ColorAdjuster:
    """Applies brightness/contrast/saturation/gamma to an RGB frame.

    Brightness, contrast and gamma collapse into a single per-channel lookup
    table (one pass).  Saturation is cross-channel, so it runs as a separate
    vectorized blend only when requested.
    """

    __slots__ = ("_lut", "_lut_applied", "_sat", "_sat_applied")

    def __init__(self, *, levels: int | None, brightness: float, contrast: float, saturation: float, gamma: float) -> None:
        self._lut = make_color_lut(levels, brightness, contrast, gamma)
        # identity is detected from the *parameters*: the float round-trip
        # through the LUT is not guaranteed to reproduce x/255*255 exactly.
        levels_identity = levels is None or levels >= 256
        self._lut_applied = levels_identity and brightness == 0.0 and contrast == 1.0 and gamma == 1.0
        self._sat = saturation
        self._sat_applied = saturation != 1.0

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self._lut_applied and not self._sat_applied:
            return rgb
        out = self._lut[rgb] if not self._lut_applied else rgb
        if self._sat_applied:
            luma = luminance_float(out)[..., np.newaxis]
            out = out.astype(np.float32)
            out = luma * 255.0 + (out - luma * 255.0) * self._sat
            out = np.clip(out, 0, 255).astype(np.uint8)
        return np.ascontiguousarray(out)


def apply_quantize(rgb: np.ndarray, levels: int | None) -> np.ndarray:
    """Quantize each channel of a uint8 RGB frame to ``levels`` steps."""
    lut = make_quant_lut(levels)
    if np.array_equal(lut, np.arange(256, dtype=np.uint8)):
        return rgb
    return lut[rgb]