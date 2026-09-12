"""Renderer factory — maps a ``RenderMode`` to a ``BaseRenderer`` instance."""

from __future__ import annotations

from .. import config
from .ascii import AsciiRenderer
from .base import BaseRenderer
from .grayscale import GrayscaleRenderer
from .halfblock import HalfBlockRenderer
from .mono import MonoRenderer


def build_renderer(cfg: config.Config) -> BaseRenderer:
    mode = cfg.mode
    if mode in (config.RenderMode.ASCII, config.RenderMode.RGB):
        return AsciiRenderer(cfg)
    if mode is config.RenderMode.GRAYSCALE:
        return GrayscaleRenderer(cfg)
    if mode is config.RenderMode.MONO:
        return MonoRenderer(cfg)
    if mode is config.RenderMode.HALFBLOCK:
        return HalfBlockRenderer(cfg)
    raise ValueError(f"no renderer for mode {mode!r}")  # pragma: no cover