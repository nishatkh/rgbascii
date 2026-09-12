<div align="center">

<img src="https://readme-typing-svg.demolab.com/?font=Fira+Code&size=32&duration=2500&pause=1200&color=FFFFFF&background=000000&center=true&vCenter=true&width=620&height=70&lines=rgbascii;Full-colour+ASCII+video+in+your+terminal;Live.+Audio-synced.+No+GUI." alt="rgbascii" />

<br />

[![Python](https://img.shields.io/badge/Python-3.11+-000000?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-required-000000?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/License-MIT-000000?style=for-the-badge&logoColor=white)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-140%20passing-000000?style=for-the-badge&logo=pytest&logoColor=white)](#development)

**Play any video as full-colour ASCII art, right in your terminal — audio included, no GUI.**

</div>

<br />

## About

`rgbascii` decodes video and audio with FFmpeg and renders each frame as coloured ASCII glyphs directly in your terminal, with the audio track driving playback timing.

- **Live & audio-synced** — FFmpeg feeds `sounddevice`; the audio cursor is the master clock.
- **Five render modes** — `ascii`, `rgb`, `grayscale`, `mono`, `halfblock`.
- **Resize-aware** — pause, seek, and restart from the keyboard; adapts to terminal resizes on the fly.
- **Terminal-safe** — alt-screen, raw input, and cursor state are restored on quit, error, or `Ctrl+C`.

<br />

## Installation

| Requirement | Install |
|---|---|
| Python 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| `ffmpeg` + `ffprobe` | `brew install ffmpeg` &nbsp;·&nbsp; `apt install ffmpeg` &nbsp;·&nbsp; `choco install ffmpeg` |

```sh
python3 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install ".[audio]"
```

> Prefer not to activate the venv? Call `.venv/bin/rgbascii` directly.

<br />

## Quick Start

```sh
rgbascii movie.mp4
```

That's it — full colour, looped, with audio. Press `q` to quit.

<br />

## Render Modes

Select with `--mode <name>`:

| Mode | Look | Best for |
|---|---|---|
| `ascii` *(default)* | Coloured, luminance-mapped glyphs | General use |
| `rgb` | Alias for `ascii` | — |
| `grayscale` | Characters with grey tones only | Monochrome look |
| `mono` | Single colour, no per-pixel colour | Stylised / artistic |
| `halfblock` | `▀` half-blocks, 2× vertical detail | Smooth, near-pixel video |

<br />

## Options

| Flag | Description |
|---|---|
| `--width N` / `--height N` | Render size in columns / rows (auto by default) |
| `--fullscreen` / `--no-fullscreen` | Alt-screen buffer (default on) / render in place |
| `--aspect F` | Vertical squeeze factor (default `0.5`) |
| `--mode MODE` | `ascii` \| `rgb` \| `grayscale` \| `mono` \| `halfblock` |
| `--charset STR` | Glyph ramp or preset (`standard`, `dense`, `minimal`, `blocks`) |
| `--invert` | Flip bright ↔ dark mapping |
| `--sample METHOD` | Cell colour sampling: `average` \| `center` \| `weighted` |
| `--color-levels N` | Posterise to N levels per channel |
| `--mono-color HEX` | Colour for `--mode mono` (default `FFFFFF`) |
| `--color` / `--no-color` | Force ANSI colour on / plain-text output |
| `--brightness F` | Brightness offset, −1…1 (default `0`) |
| `--contrast F` | Contrast multiplier (default `1`) |
| `--saturation F` | Colour saturation, 0 = greyscale, 1 = normal |
| `--gamma F` | Gamma correction (default `1`) |
| `--loop` / `--no-loop` | Loop forever (default) / play once then exit |
| `--start S` / `--end E` | Play seconds `S`–`E` |
| `--fps N` | Target frame rate |
| `--no-audio` | Disable audio (video clock only) |
| `--clock MODE` | Clock source: `auto` \| `audio` \| `video` |
| `--buffer-ms MS` | Decode-ahead queue (default `120`) |
| `--catchup-ms MS` | Lag threshold before re-seek (default `350`) |
| `--frames N` | Render N frames, then exit |
| `--debug` | Print FPS and drop stats |
| `--version` | Print version |

**Examples:**

```sh
rgbascii movie.mp4 --width 120 --mode halfblock
rgbascii movie.mp4 --mode grayscale --charset dense
rgbascii movie.mp4 --mono-color FF00CC --start 60 --end 120
rgbascii movie.mp4 --no-audio --fps 15 --debug
```

<br />

## Keyboard Controls

Press once while playing — no `Enter` needed.

| Key | Action |
|---|---|
| `Space` / `p` | Pause / resume |
| `q` | Quit |
| `←` / `→` | Seek back / forward 5 s |
| `+` / `-` | Finer / coarser grid |
| `r` | Restart |

<br />

## Demo

<div align="center">
<!-- <video src="assets/demo/rgbascii-demo.mp4" width="620" controls muted loop autoplay playsinline></video> -->
</div>

Drop a recording at `assets/demo/rgbascii-demo.mp4`, then uncomment the player above.

```sh
mkdir -p assets/demo
ffmpeg -i your_recording.webm -vf "scale=480:-1,fps=24" -c:v libx264 -pix_fmt yuv420p -movflags +faststart assets/demo/rgbascii-demo.mp4
```

<br />

## Troubleshooting

| Symptom | Fix |
|---|---|
| No audio | Install with `".[audio]"`, confirm `ffmpeg` is on `PATH`, or use `--no-audio` |
| Garbled colours | Terminal may lack TrueColor — try `--no-color` or `--mode mono` |
| Slow / dropped frames | Lower `--width`, or raise `--catchup-ms 500` |
| Wrong size | Force it: `rgbascii movie.mp4 --width 80 --height 24` |

**Exit codes:** `0` ended or quit &nbsp;·&nbsp; `1` runtime error &nbsp;·&nbsp; `2` usage error &nbsp;·&nbsp; `130` `Ctrl+C`

<br />

## Development

```sh
pip install -e ".[dev]"
pytest                    # all 140 tests
python benchmarks/bench_render.py
```

<br />

## License

Released under the [MIT License](LICENSE).

<div align="center">

---

<sub>Built with `numpy` · `ffmpeg` · `sounddevice`</sub>

</div>
