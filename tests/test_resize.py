"""Resize: dimensions, aspect handling, sampling correctness."""

from __future__ import annotations

import numpy as np
import pytest

from rgbascii.processing.resize import resize


def test_downscale_shape():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    out = resize(frame, 40, 20, method="average")
    assert out.shape == (20, 40, 3)
    assert out.dtype == np.uint8


def test_upscale_shape():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    out = resize(frame, 25, 30, method="nearest")
    assert out.shape == (30, 25, 3)


def test_same_size_returns_copy():
    frame = np.full((8, 8, 3), 7, dtype=np.uint8)
    out = resize(frame, 8, 8)
    assert out.shape == frame.shape
    out[0, 0, 0] = 99
    assert frame[0, 0, 0] == 7  # original untouched


def test_average_of_constant_is_constant():
    frame = np.full((40, 40, 3), 123, dtype=np.uint8)
    out = resize(frame, 10, 10, method="average")
    assert np.all(out == 123)


def test_average_matches_numpy_mean_on_integer_ratio():
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 256, (40, 40, 3), dtype=np.uint8)
    out = resize(frame, 10, 10, method="average")
    # exact 4x4 block means
    expected = frame.reshape(10, 4, 10, 4, 3).mean(axis=(1, 3))
    assert np.allclose(out.astype(float), expected, atol=1.0)


def test_center_sampling_picks_representative_pixel():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[5, 5] = (255, 255, 255)
    out = resize(frame, 1, 1, method="nearest")
    assert tuple(out[0, 0]) == (255, 255, 255)


def test_average_reduces_noise():
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    frame[::2, ::2] = 255  # half bright
    avg = resize(frame, 5, 5, method="average")
    near = resize(frame, 5, 5, method="nearest")
    assert avg.mean() < near.mean()


def test_rejects_bad_shape():
    with pytest.raises(TypeError):
        resize(np.zeros((4, 4), dtype=np.uint8), 2, 2)


def test_rejects_bad_dimensions():
    with pytest.raises(ValueError):
        resize(np.zeros((4, 4, 3), dtype=np.uint8), 0, 2)