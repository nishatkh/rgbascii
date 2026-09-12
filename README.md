# <p align="center"><img src="assets/logo.svg" alt="rgbascii" width="300">

Play any video as colourful ASCII art right in your terminal — audio included, no GUI required.</p>

---


<p align="center"><img src="https://i.postimg.cc/ZRcHYny3/Screenshot-2026-09-12-at-7-57-03-PM.png" alt="rgbascii in action" width="700"></p>
```

---

<p align="center"><img src="assets/headings/about.svg" alt="ABOUT" width="260"></p>

- **Fast** — a vectorised NumPy pipeline; decode runs ahead on a queue and auto re-seeks on lag.
- **Audio-synced** — FFmpeg feeds `sounddevice`; the audio cursor is the master clock.
- **5 render modes** — `ascii`, `rgb`, `grayscale`, `mono` and `halfblock`.
- **Terminal-safe** — alt screen, raw input and reset are restored on quit, error, or Ctrl+C.

---

<p align="center"><img src="assets/headings/install.svg" alt="INSTALL" width="361"></p>

### Step 1 — Prerequisites

| Requirement | Check with | Install |
|---|---|---|
| **Python 3.11+** | `python3 --version` | [python.org](https://www.python.org/downloads/) |
| **ffmpeg + ffprobe** | `ffmpeg -version` | `brew install ffmpeg` (macOS) · `sudo apt install ffmpeg` (Ubuntu/Debian) · `choco install ffmpeg` (Windows) |

### Step 2 — Create a virtual environment

```sh
cd /path/to/rgbascii
python3 -m venv .venv
```

### Step 3 — Activate it

```sh
source .venv/bin/activate            # macOS / Linux (bash, zsh)
source .venv/bin/activate.fish     # macOS / Linux (fish shell)
.venv\Scripts\activate             # Windows (Command Prompt)
.venv\Scripts\Activate.ps1         # Windows (PowerShell)
```

### Step 4 — Install with audio support

```sh
pip install ".[audio]"
```

If that fails (e.g. no internet access), install the base package, then add audio separately:

```sh
pip install .
pip install sounddevice
```

### Step 5 — Verify

```sh
rgbascii --version
```

> No activation needed? Call `.venv/bin/rgbascii` (or `.venv\Scripts\rgbascii.exe` on Windows).

---

<p align="center"><img src="assets/headings/quickstart.svg" alt="QUICK START" width="563"></p>

```sh
rgbascii movie.mp4
```

The video plays in full colour, loops forever, with audio. Press **q** to quit.

---

<p align="center"><img src="assets/headings/modes.svg" alt="MODES" width="260"></p>

Pass any mode with `--mode <name>`:

| Mode | Look | Best for |
|---|---|---|
| `ascii` (default) | Coloured luminance-mapped glyphs | General use |
| `rgb` | Alias for `ascii` | — |
| `grayscale` | Characters + grey tones only | Monochrome look |
| `mono` | Single colour, no per-pixel colour | Stylised / artistic |
| `halfblock` | `▀` blocks — 2× vertical detail | Smooth, near-pixel video |

---

<p align="center"><img src="assets/headings/options.svg" alt="OPTIONS" width="361"></p>

| Flag | What it does |
|---|---|
| `--width N` / `--height N` | Render size in columns / rows (auto by default) |
| `--fullscreen` / `--no-fullscreen` | Alt-screen buffer (default on) / render in place |
| `--aspect F` | Vertical squeeze factor (default `0.5`) |
| `--mode MODE` | `ascii` \| `rgb` \| `grayscale` \| `mono` \| `halfblock` |
| `--charset STR` | Glyph ramp or preset (`standard` `dense` `minimal` `blocks`) |
| `--invert` | Flip bright↔dark mapping |
| `--sample METHOD` | Cell colour: `average` \| `center` \| `weighted` |
| `--color-levels N` | Posterise to N levels per channel |
| `--mono-color HEX` | Colour for `--mode mono` (default `FFFFFF`) |
| `--color` / `--no-color` | Force ANSI colour on / plain-text output |
| `--brightness F` | Add brightness (−1…1, default 0) |
| `--contrast F` | Multiply contrast (default 1) |
| `--saturation F` | Colour saturation (0 = greyscale, 1 = normal) |
| `--gamma F` | Gamma correction (default 1) |
| `--loop` / `--no-loop` | Loop forever (default) / play once then exit |
| `--start S` / `--end E` | Play seconds S–E |
| `--fps N` | Target frame rate |
| `--no-audio` | Disable audio (video clock only) |
| `--clock MODE` | Clock: `auto` \| `audio` \| `video` |
| `--buffer-ms MS` | Decode-ahead queue (default `120`) |
| `--catchup-ms MS` | Lag before re-seek (default `350`) |
| `--frames N` | Render N frames then exit |
| `--debug` | Print FPS and drop stats |
| `--version` | Print version |

```sh
rgbascii movie.mp4 --width 120 --mode halfblock
rgbascii movie.mp4 --mode grayscale --charset dense
rgbascii movie.mp4 --mono-color FF00CC --start 60 --end 120
rgbascii movie.mp4 --no-audio --fps 15 --debug
```

---

<p align="center"><img src="assets/headings/keys.svg" alt="KEYS" width="210"></p>

Press once while playing — no Enter needed:

| Key | Action |
|---|---|
| `Space` / `p` | Pause / resume |
| `q` | Quit |
| `←` / `→` | Seek back / forward 5 s |
| `+` / `-` | Finer / coarser grid |
| `r` | Restart |

---

<p align="center"><img src="assets/headings/issues.svg" alt="ISSUES" width="311"></p>

- **No audio** — install with `".[audio]"`, confirm `ffmpeg` is on PATH, or force `--no-audio`.
- **Garbled colours** — terminal may lack TrueColor: use `--no-color` or `--mode mono`.
- **Slow / dropped frames** — lower `--width`, or raise `--catchup-ms 500`.
- **Wrong size** — force it: `rgbascii movie.mp4 --width 80 --height 24`.

Exit codes: `0` ended or quit · `1` runtime error · `2` usage error · `130` Ctrl+C.

---

<p align="center"><img src="assets/headings/dev.svg" alt="DEV" width="160"></p>

```sh
pip install -e ".[dev]"
pytest                    # all 140 tests
python benchmarks/bench_render.py
```

---

<p align="center"><img src="assets/headings/license.svg" alt="LICENSE" width="361"></p>

MIT — see [`LICENSE`](LICENSE).
