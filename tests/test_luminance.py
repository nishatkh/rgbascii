"""Luminance: Rec.709 correctness and contrast with the naive formula."""

from __future__ import annotations

import numpy as np
import pytest

from rgbascii.processing.luminance import luminance, luminance_float


def test_black_is_zero():
    assert luminance(np.array([[[0, 0, 0]]], dtype=np.uint8))[0, 0] == 0


def test_white_is_255():
    assert luminance(np.array([[[255, 255, 255]]], dtype=np.uint8))[0, 0] == 255


def test_rec709_weights():
    # pure green is far brighter than pure blue under Rec.709
    green = luminance(np.array([[[0, 255, 0]]], dtype=np.uint8))[0, 0]
    blue = luminance(np.array([[[0, 0, 255]]], dtype=np.uint8))[0, 0]
    assert green == pytest.approx(182, abs=1)
    assert blue == pytest.approx(18, abs=1)
    assert green > blue


def test_red_weight():
    red = luminance(np.array([[[255, 0, 0]]], dtype=np.uint8))[0, 0]
    assert red == pytest.approx(54, abs=1)


def test_known_mid_gray():
    # 128,128,128 -> ~128 under any sane weights
    val = luminance(np.array([[[128, 128, 128]]], dtype=np.uint8))[0, 0]
    assert val == pytest.approx(128, abs=1)


def test_naive_differs_from_rec709():
    px = np.array([[[255, 0, 0]]], dtype=np.uint8)
    assert int(luminance(px)[0, 0]) != int(luminance(px, naive=True)[0, 0])
    assert luminance(px, naive=True)[0, 0] == pytest.approx(85, abs=1)


def test_luminance_float_range():
    frame = np.random.default_rng(0).integers(0, 256, (10, 10, 3), dtype=np.uint8)
    out = luminance_float(frame)
    assert out.shape == (10, 10)
    assert out.dtype == np.float32
    assert 0.0 <= out.min() and out.max() <= 1.0


def test_luminance_matches_manual_formula():
    frame = np.random.default_rng(1).integers(0, 256, (4, 4, 3), dtype=np.uint8)
    out = luminance(frame).astype(float)
    manual = np.clip(frame.astype(float) @ [0.2126, 0.7152, 0.0722], 0, 255)
    assert np.allclose(out, manual, atol=1.0)