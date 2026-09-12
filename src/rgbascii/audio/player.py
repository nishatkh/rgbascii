"""Sound-based audio player.

Bridges an ``ffmpeg`` decoder and ``sounddevice``:

* an ``ffmpeg`` child decodes the audio track to packed little-endian float
  PCM (stereo, 48 kHz) into a bounded queue fed by a reader thread;
* a PortAudio ``OutputStream`` pulls buffers out of that queue from its
  realtime callback (never blocking: an empty queue is answered with silence
  and counted as an underrun, and a full queue drops the oldest buffer to keep
  latency bounded);
* position is the PortAudio sample clock plus the start offset, which the
  PlaybackClock uses as the master clock for A/V sync.

The dependency is optional: ``audio.backend.make_audio()` only imports this
module when ``sounddevice`` is importable.
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from typing import Optional

import numpy as np

from ..errors import AudioError
from .backend import AudioBackend

BLOCKSIZE = 2048
OUT_SAMPLE_RATE = 48000
OUT_CHANNELS = 2


class SoundDeviceAudioPlayer(AudioBackend):
    def __init__(self, source_path: str, *, source_rate: int | None = None) -> None:
        import sounddevice as sd  # deferred import: optional dependency

        self._sd = sd
        self._source_path = source_path
        self._source_rate = source_rate or OUT_SAMPLE_RATE
        self._queue: queue.Queue = queue.Queue(maxsize=64)
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stream: Optional[sd.OutputStream] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._seek_offset = 0.0
        self._end: float | None = None
        self._playing = False
        self._paused = False
        self._played_frames = 0
        self._latency = 0.0
        self._underline = 0
        self._dropped = 0
        self._ffmpeg = shutil.which("ffmpeg")
        if not self._ffmpeg:
            raise AudioError("ffmpeg not found; cannot decode audio")

    # -- lifecycle -------------------------------------------------------------

    def start(self, offset: float = 0.0, end: float | None = None) -> None:
        with self._lock:
            self._stop.clear()
            self._seek_offset = offset
            self._end = end
            self._queue = queue.Queue(maxsize=64)
            self._proc, self._thread = self._spawn(offset, end)
            try:
                self._open_stream()
            except AudioError:
                self._teardown()
                raise

    def seek(self, seconds: float) -> None:
        with self._lock:
            self._seek_offset = seconds
            self._stop.set()
            self._teardown()
            self._stop.clear()
            self._queue = queue.Queue(maxsize=64)
            self._proc, self._thread = self._spawn(seconds, self._end)
            try:
                self._open_stream()
            except AudioError:
                self._teardown()
                raise

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            self._playing = False
            self._teardown()

    # -- controls --------------------------------------------------------------

    def pause(self) -> None:
        self._paused = True
        self._playing = False

    def resume(self) -> None:
        self._playing = True
        self._paused = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def dropped(self) -> int:
        return self._dropped

    # -- position --------------------------------------------------------------

    def position(self) -> Optional[float]:
        if not self._playing:
            return None
        if self._stream is None:
            return None
        # PortAudio's stream.time is the *host reference* clock (uptime, in
        # seconds), not time since this stream started, so it can never be used
        # as a playback cursor.  Track the played sample count instead, and
        # back it off by the output latency so the cursor points at what the
        # ear hears rather than what's still in the pipeline.
        played = self._played_frames / OUT_SAMPLE_RATE - self._latency
        return self._seek_offset + max(0.0, played)

    # -- stream plumbing ---------------------------------------------------------

    def _open_stream(self) -> None:
        stream = None
        try:
            stream = self._sd.OutputStream(
                samplerate=OUT_SAMPLE_RATE,
                channels=OUT_CHANNELS,
                dtype="float32",
                blocksize=BLOCKSIZE,
                callback=self._callback,
                latency="high",
            )
            # Reset frame counter and mark as playing BEFORE stream.start() so
            # that the PortAudio callback (which fires on a real-time thread the
            # instant start() is called) sees _playing=True and begins counting
            # frames immediately.  Setting it afterward caused a race where the
            # first N callbacks bailed out and _played_frames stayed 0, making
            # position() always return None.
            self._played_frames = 0
            self._paused = False
            self._playing = True
            try:
                self._latency = float(stream.latency) or 0.0
            except Exception:
                self._latency = 0.0
            stream.start()
        except Exception as exc:  # pragma: no cover - device dependent
            self._playing = False
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            raise AudioError(f"could not open audio output: {exc}") from None
        self._stream = stream

    def _spawn(self, offset: float, end: float | None) -> tuple[subprocess.Popen, threading.Thread]:
        cmd = [self._ffmpeg, "-v", "error"]
        if offset > 0:
            cmd += ["-ss", f"{offset:.6f}"]
        cmd += ["-i", self._source_path]
        if end is not None:
            cmd += ["-t", f"{max(0.0, end - offset):.6f}"]
        cmd += [
            "-vn",
            "-f", "f32le",
            "-ac", str(OUT_CHANNELS),
            "-ar", str(OUT_SAMPLE_RATE),
            "-",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        thread = threading.Thread(target=self._pump, args=(proc,), daemon=True)
        thread.start()
        return proc, thread

    def _finish(self) -> None:
        """Audio stream reached the end of its range: stop consuming time."""
        self._playing = False
        self._paused = False

    def _pump(self, proc: subprocess.Popen) -> None:
        block_bytes = BLOCKSIZE * OUT_CHANNELS * 4
        blob = bytearray(block_bytes)
        try:
            while not self._stop.is_set():
                if proc.stdout is None:
                    break
                off = 0
                while off < block_bytes:
                    chunk = proc.stdout.read(block_bytes - off)
                    if not chunk:
                        break
                    blob[off : off + len(chunk)] = chunk
                    off += len(chunk)
                if off == 0:
                    # True EOF: no data at all this iteration.
                    break
                if off < block_bytes:
                    # Partial final block: zero-pad so all audio is delivered.
                    blob[off:] = b"\x00" * (block_bytes - off)
                samples = np.frombuffer(blob, dtype=np.float32).reshape(-1, OUT_CHANNELS)
                # Enqueue with backpressure: block (with short sleep) rather than
                # dropping so the callback can drain at its own pace.
                while not self._stop.is_set():
                    try:
                        self._queue.put(samples.copy(), timeout=0.05)
                        break
                    except queue.Full:
                        pass  # wait for callback to drain the queue
                if off < block_bytes:
                    # Partial block was the last one; exit after enqueuing it.
                    break
            # All data is queued; wait for the callback to drain it before
            # declaring the stream finished so _playing stays True while audio
            # is still being heard.
            while not self._stop.is_set() and not self._queue.empty():
                import time as _time
                _time.sleep(0.02)
        finally:
            if not self._stop.is_set():
                self._finish()

            try:
                proc.terminate()
            except Exception:
                pass

    def _callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:  # type: ignore[no-untyped-def]
        if not self._playing or self._paused:
            outdata.fill(0.0)
            return
        self._played_frames += outdata.shape[0]
        try:
            data = self._queue.get_nowait()
        except queue.Empty:
            if status:
                self._underline += 1
            outdata.fill(0.0)
            return
        if data is None:
            outdata.fill(0.0)
            return
        n = min(frames, data.shape[0])
        outdata[:n] = data[:n]
        if n < frames:
            outdata[n:] = 0.0

    def _teardown(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        proc, thread = self._proc, self._thread
        self._proc = None
        self._thread = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if thread is not None:
            thread.join(timeout=2)