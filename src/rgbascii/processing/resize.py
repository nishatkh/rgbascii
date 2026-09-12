"""Vectorized frame resizing.

Two sampling strategies, both implemented with NumPy so we never loop over
pixels in Python:

* ``nearest`` — maps the centre of every output cell onto the closest source
  pixel (fast, "crisp", used by the ``center`` cell strategy).
* ``average`` — exact area-average over the source pixels each output cell
  covers (higher quality, used by the ``average`` and ``weighted`` cell
  strategies).  Axis-wise summation uses ``np.add.reduceat`` over precomputed
  boundary slices, so it stays vectorized for arbitrary in/out ratios.

A source is never up-scaled by averaging: growing a dimension falls back to
nearest so we do not manufacture detail out of thin air.
"""

from __future__ import annotations

import numpy as np


def _center_indices(in_len: int, out_len: int) -> np.ndarray:
    """Source index whose centre contains output cell centre *i*."""
    if in_len == out_len:
        return np.arange(out_len, dtype=np.int64)
    # integer form of floor((i + 0.5) * in_len / out_len)
    idx = ((2 * np.arange(out_len, dtype=np.int64) + 1) * in_len) // (2 * out_len)
    return np.minimum(idx, in_len - 1)


def _nearest_axis(arr: np.ndarray, out_len: int, axis: int) -> np.ndarray:
    idx = _center_indices(arr.shape[axis], out_len)
    return np.take(arr, idx, axis=axis)


def _average_axis(arr: np.ndarray, out_len: int, axis: int) -> np.ndarray:
    """Exact area average along one axis (downscale only)."""
    in_len = arr.shape[axis]
    if out_len >= in_len:
        return _nearest_axis(arr, out_len, axis)
    bounds = (np.arange(out_len + 1, dtype=np.int64) * in_len) // out_len
    reduced = np.add.reduceat(arr, bounds[:-1], axis=axis)
    counts = np.diff(bounds).astype(np.float32)
    shape = [1] * arr.ndim
    shape[axis] = out_len
    counts = counts.reshape(shape)
    return reduced / counts


def resize(
    frame: np.ndarray,
    width: int,
    height: int,
    method: str = "average",
) -> np.ndarray:
    """Resize an ``(H, W, 3)`` uint8 RGB frame to ``(height, width, 3)``.

    Returns a fresh uint8 array.  ``method`` is one of ``nearest`` / ``average``
    (``weighted`` aliases ``average``).
    """
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        raise TypeError(f"expected an (H, W, 3) array, got {getattr(frame, 'shape', None)!r}")

    if width <= 0 or height <= 0:
        raise ValueError(f"resize dimensions must be positive, got {width}x{height}")

    in_h, in_w = frame.shape[:2]
    if width == in_w and height == in_h:
        return frame.copy()

    if method in ("average", "weighted"):
        work = frame.astype(np.float32)
        work = _average_axis(work, height, 0)
        work = _average_axis(work, width, 1)
        return np.ascontiguousarray(np.clip(work, 0, 255).astype(np.uint8))

    if method == "nearest":
        out = _nearest_axis(frame, height, 0)
        out = _nearest_axis(out, width, 1)
        return np.ascontiguousarray(out)

    raise ValueError(f"unknown resize method {method!r} (choose from nearest, average)")