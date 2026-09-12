"""Regression test: raw pipe reads must not be assumed to fill a whole frame.

`io.FileIO.read(n)` returns as soon as the kernel hands us *any* bytes
(typically a partial 64KiB chunk on macOS), so the pump must accumulate.
"""

from __future__ import annotations

import subprocess

import numpy as np
import pytest

from rgbascii.video.ffmpeg import FFmpegVideoDecoder, parse_rational, probe_metadata


pytestmark = pytest.mark.requires_ffmpeg


def test_probe_metadata(synthetic_video):
    meta = probe_metadata(synthetic_video)
    assert meta.width > 0 and meta.height > 0
    assert meta.fps >= 1
    assert meta.duration > 0
    assert meta.has_audio


def test_parse_rational():
    assert parse_rational("30000/1001") == pytest.approx(29.97, rel=1e-2)
    assert parse_rational("30") == 30.0
    assert parse_rational("") == 30.0
    assert parse_rational("junk") == 30.0


def _collect(path, end, limit=10):
    dec = FFmpegVideoDecoder(path, target_fps=None, queue_size=16)
    idxs, frames = [], []
    for idx, frame in dec.frames(end=end):
        idxs.append(idx)
        frames.append(frame)
        if len(frames) >= limit:
            break
    if len(frames) < limit:
        dec.stop()
    return idxs, frames


def test_decoder_streams_several_frames(synthetic_video):
    idxs, frames = _collect(synthetic_video, end=4.0, limit=8)
    assert len(frames) == 8
    assert idxs == list(range(8))
    assert frames[0].shape[2] == 3
    assert frames[0].dtype == np.uint8


def test_decoder_hits_eof_at_end(synthetic_video):
    dec = FFmpegVideoDecoder(synthetic_video, target_fps=None, queue_size=4)
    idxs = [idx for idx, _ in dec.frames(end=1.5)]
    dec.stop()
    assert len(idxs) >= 1
    assert all(b > a for a, b in zip(idxs, idxs[1:]))


def test_decoder_seek_gives_subsequent_indices(synthetic_video):
    dec = FFmpegVideoDecoder(synthetic_video, target_fps=None, queue_size=4)
    idxs = [idx for idx, _ in dec.frames(start=0.5, end=1.5)]
    dec.stop()
    assert len(idxs) >= 1
    assert idxs[0] >= 1  # 30fps source, so 0.5s is at least frame 15-ish