"""FFmpeg-backed video decoder.

Single source of truth for spawning FFmpeg pipelines:

* ``probe_metadata()`` shells out to ``ffprobe`` once at startup.
* ``FFmpegVideoDecoder`` streams ``rgb24`` raw frames from an ``ffmpeg``
  child process into a bounded queue fed by a background thread, so decoding
  never stalls rendering as long as the renderer keeps up.

`-ss` before `-i` gives fast (keyframe-accurate) input seeking, which is what
we want for playback skips; the media is pre-normalized to a constant target
FPS with the ``fps`` video filter so frame indices map 1:1 onto time.
``scale`` is applied to cap the decode pipeline width (keeps the pipe cheap)
while preserving the source aspect ratio.

A reader never holds the child process hostage: EOF is detected by the reader
thread *finishing* plus an empty queue, no special sentinel is needed, and a
``restart()`` simply replaces the process + queue wholesale.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from typing import Iterator, Optional

import numpy as np

from ..errors import FfmpegNotFoundError, VideoError
from .decoder import VideoDecoder
from .metadata import VideoMetadata

DECODE_BPP = 3  # rgb24
WORK_WIDTH_CAP = 640  # decode pipeline pixel budget keeps the pipe fast


def _find_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise FfmpegNotFoundError(
            "ffmpeg and ffprobe were not found on PATH. "
            "Install ffmpeg (apt install ffmpeg / brew install ffmpeg / choco install ffmpeg)."
        )
    return ffmpeg, ffprobe


def parse_rational(value: str | None, default: float = 30.0) -> float:
    """Parse a fraction like ``30000/1001`` or a plain float."""
    if not value:
        return default
    try:
        if "/" in value:
            num, den = value.split("/")
            return float(num) / float(den)
        return float(value)
    except (ValueError, ZeroDivisionError):
        return default


def probe_metadata(path: str) -> VideoMetadata:
    ffmpeg, ffprobe = _find_ffmpeg()
    if not os.path.exists(path):
        raise VideoError(f"input file not found: {path}")
    if os.path.isdir(path):
        raise VideoError(f"input is a directory, not a video: {path}")

    cmd = [
        ffprobe, "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.SubprocessError, OSError) as exc:
        raise VideoError(f"failed to probe {path!r}: {exc}") from None
    if proc.returncode != 0:
        raise VideoError(f"ffprobe could not read {path!r}: {proc.stderr.strip()}")

    try:
        info = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        raise VideoError(f"ffprobe returned unparsable output for {path!r}") from None

    streams = info.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if vstream is None:
        raise VideoError(f"no video stream found in {path!r}")

    width = int(vstream.get("width") or 0)
    height = int(vstream.get("height") or 0)
    fps = parse_rational(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate"))

    frame_count: Optional[int] = None
    if vstream.get("nb_frames") not in (None, "N/A"):
        try:
            frame_count = int(vstream["nb_frames"])
        except (TypeError, ValueError):
            frame_count = None

    duration: Optional[float] = None
    for candidate in (vstream.get("duration"), info.get("format", {}).get("duration")):
        if candidate and candidate != "N/A":
            try:
                duration = float(candidate)
                break
            except (TypeError, ValueError):
                continue

    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    sample_rate: Optional[int] = None
    if astream is not None and astream.get("sample_rate"):
        try:
            sample_rate = int(astream["sample_rate"])
        except (TypeError, ValueError):
            sample_rate = None

    return VideoMetadata(
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration=duration,
        sample_rate=sample_rate,
        has_audio=astream is not None,
        codec=str(vstream.get("codec_name") or "unknown"),
    )


def _work_geometry(meta: VideoMetadata) -> tuple[int, int]:
    """Decoded size: source aspect preserved, width capped for throughput."""
    w, h = meta.width, meta.height
    if w <= 0 or h <= 0:
        return 320, 240
    if w > WORK_WIDTH_CAP:
        scale = WORK_WIDTH_CAP / w
        work_w = WORK_WIDTH_CAP
        work_h = max(2, int(h * scale / 2) * 2)
    else:
        work_w, work_h = w, h
    return work_w, work_h


class FFmpegVideoDecoder(VideoDecoder):
    """Streams rgb24 frames from an ffmpeg child on a bounded queue."""

    def __init__(self, path: str, target_fps: float | None, *, queue_size: int = 8) -> None:
        self._path = path
        self._target_fps = target_fps or None
        self._queue_size = queue_size
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._dropped = 0
        self._base_index = 0

        self._ffmpeg, _ = _find_ffmpeg()
        self._meta = probe_metadata(path)
        self._work_w, self._work_h = _work_geometry(self._meta)
        self._fps = target_fps or self._meta.fps
        self._frame_bytes = self._work_w * self._work_h * DECODE_BPP

    # -- protocol ------------------------------------------------------------

    def metadata(self) -> VideoMetadata:
        return self._meta

    def frames(
        self,
        *,
        start: float = 0.0,
        end: float | None = None,
    ) -> Iterator[tuple[int, np.ndarray]]:
        proc, thread, q, base_index = self._spawn(start, end)
        try:
            while not self._stop_event.is_set():
                try:
                    item = q.get(timeout=0.2)
                except queue.Empty:
                    if not thread.is_alive():
                        break
                    continue
                if item is None:  # explicit EOF built by restart
                    break
                yield (int(base_index) + int(item[0]), item[1])
        finally:
            if proc is not None:
                self._teardown(proc, thread)

    def restart(self, at_seconds: float = 0.0) -> None:
        with self._lock:
            self._stop_event.set()
            self._teardown(self._proc, self._thread)

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            self._teardown(self._proc, self._thread)

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def work_width(self) -> int:
        return self._work_w

    @property
    def work_height(self) -> int:
        return self._work_h

    # -- internals -----------------------------------------------------------

    def _spawn(self, start: float, end: float | None) -> tuple[subprocess.Popen, "threading.Thread", "queue.Queue", int]:
        with self._lock:
            self._stop_event.clear()
            self._dropped = 0
            base_index = int(round(start * self._fps))
            frames_since = [0]  # mutable counter shared with the pump thread

            cmd = self._build_cmd(start, end)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
            q: queue.Queue = queue.Queue(maxsize=self._queue_size)
            thread = threading.Thread(
                target=self._pump, args=(proc, q, base_index, frames_since), daemon=True
            )
            thread.start()
            self._proc, self._thread, self._queue = proc, thread, q
            return proc, thread, q, base_index

    def _build_cmd(self, start: float, end: float | None) -> list[str]:
        cmd = [self._ffmpeg, "-v", "error"]
        if start > 0:
            cmd += ["-ss", f"{start:.6f}"]
        cmd += ["-i", self._path]
        if end is not None:
            remaining = max(0.0, end - start)
            cmd += ["-t", f"{remaining:.6f}"]
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24"]
        cmd += ["-vf", f"fps={self._fps:.6f},scale={self._work_w}:{self._work_h}"]
        cmd += ["-"]
        return cmd

    def _pump(self, proc: subprocess.Popen, q: queue.Queue, base_index: int, frames_since: list[int]) -> None:
        stdout = proc.stdout
        size = self._frame_bytes
        blob = bytearray(size)
        try:
            while not self._stop_event.is_set():
                if stdout is None:
                    break
                off = 0
                while off < size:
                    chunk = stdout.read(size - off)
                    if not chunk or self._stop_event.is_set():
                        break
                    blob[off : off + len(chunk)] = chunk
                    off += len(chunk)
                if off < size:
                    break  # EOF in the middle of a frame: stream is done
                frame = np.frombuffer(blob, dtype=np.uint8).reshape(self._work_h, self._work_w, 3).copy()
                item = (frames_since[0], frame)
                frames_since[0] += 1
                enqueued = False
                while not enqueued:
                    try:
                        q.put(item, timeout=0.1)
                        enqueued = True
                    except queue.Full:
                        if self._stop_event.is_set():
                            break
                if not enqueued:
                    self._dropped += 1  # abandoned only when shutting down
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    def _teardown(self, proc, thread) -> None:
        self._stop_event.set()  # stop_event is never cleared inside _teardown
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (subprocess.SubprocessError, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass
        if thread is not None:
            thread.join(timeout=2)