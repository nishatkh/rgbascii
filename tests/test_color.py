"""Color: quantization and image adjustments."""

from __future__ import annotations

import numpy as np

from rgbascii.processing.color import ColorAdjuster, apply_quantize, make_color_lut, make_quant_lut


def test_quant_lut_identity():
    lut = make_quant_lut(None)
    assert np.array_equal(lut, np.arange(256, dtype=np.uint8))


def test_quant_lut_levels():
    lut = make_quant_lut(2)
    assert set(int(v) for v in lut) == {0, 255}
    lut4 = make_quant_lut(4)
    assert len(set(int(v) for v in lut4)) == 4


def test_quantize_frame():
    frame = np.array([[[10, 120, 250]]], dtype=np.uint8)
    out = apply_quantize(frame, 2)
    assert tuple(out[0, 0]) == (0, 0, 255)


def test_quantize_four_levels():
    frame = np.array([[[0, 85, 170]]], dtype=np.uint8)
    out = apply_quantize(frame, 4)
    # levels map to 0, 85, 170, 255
    assert tuple(out[0, 0]) == (0, 85, 170)


def test_quantize_identity_returns_same():
    frame = np.array([[[1, 2, 3]]], dtype=np.uint8)
    assert apply_quantize(frame, None) is frame


def test_adjuster_identity_is_noop():
    frame = np.random.default_rng(0).integers(0, 256, (6, 6, 3), dtype=np.uint8)
    adj = ColorAdjuster(levels=None, brightness=0.0, contrast=1.0, saturation=1.0, gamma=1.0)
    assert adj.apply(frame) is frame


def test_brightness_increases_values():
    frame = np.full((2, 2, 3), 100, dtype=np.uint8)
    adj = ColorAdjuster(levels=None, brightness=0.2, contrast=1.0, saturation=1.0, gamma=1.0)
    out = adj.apply(frame)
    assert out.mean() > frame.mean()


def test_gamma_endpoints_fixed():
    lut = make_color_lut(None, 0.0, 1.0, 2.2)
    assert lut[0] == 0
    assert lut[255] == 255


def test_gamma_brightens_midtones():
    lut = make_color_lut(None, 0.0, 1.0, 2.2)
    assert int(lut[128]) > 128  # gamma > 1 brightens midtones


def test_contrast_around_midpoint():
    frame = np.array([[[64, 128, 192]]], dtype=np.uint8)
    adj = ColorAdjuster(levels=None, brightness=0.0, contrast=2.0, saturation=1.0, gamma=1.0)
    out = adj.apply(frame)[0, 0]
    assert out[1] == 128
    assert out[0] < 64
    assert out[2] > 192


def test_saturation_zero_gives_gray():
    frame = np.array([[[255, 0, 0]]], dtype=np.uint8)
    adj = ColorAdjuster(levels=None, brightness=0.0, contrast=1.0, saturation=0.0, gamma=1.0)
    out = adj.apply(frame)[0, 0]
    assert out[0] == out[1] == out[2]


def test_saturation_boost_keeps_luma_reasonable():
    frame = np.array([[[200, 100, 50]]], dtype=np.uint8)
    adj = ColorAdjuster(levels=None, brightness=0.0, contrast=1.0, saturation=1.5, gamma=1.0)
    out = adj.apply(frame)[0, 0]
    assert (out[0], out[1], out[2]) != (200, 100, 50)