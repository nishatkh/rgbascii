"""Shared event plumbing.

A single module-level queue is the one small global in the app: the input
thread publishes key events and the playback loop consumes them.  A module
global keeps the terminal/input layer and the playback engine decoupled
without threading a queue through every constructor.
"""

from __future__ import annotations

import queue

event_queue: "queue.Queue[str]" = queue.Queue()


def drain() -> list[str]:
    out: list[str] = []
    while True:
        try:
            out.append(event_queue.get_nowait())
        except queue.Empty:
            return out