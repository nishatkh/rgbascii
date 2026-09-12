# rgbascii

> **Play any video as colourful ASCII art, right inside your terminal — with audio.**

```
       .::::::==------:.......%%%%%%%%*******+*#####%@@@@@@@
       .:::::==-------:...... %%%%%%%*******+*#####%@@@@@@
```

`rgbascii` decodes a video with FFmpeg, maps every frame to ASCII characters with
24-bit ANSI True Color, and renders it in real time — audio included, no GUI required.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Install in 60 seconds](#install-in-60-seconds)
3. [Quick start](#quick-start)
4. [Render modes](#render-modes)
5. [All options](#all-options)
6. [Keyboard controls](#keyboard-controls)
7. [Tips & recipes](#tips--recipes)
8. [Troubleshooting](#troubleshooting)
9. [Exit codes](#exit-codes)

---

## Requirements

| Requirement | How to install |
|---|---|
| **Python 3.11 or newer** | [python.org](https://www.python.org/downloads/) |
| **ffmpeg + ffprobe** | `brew install ffmpeg` · `apt install ffmpeg` · `choco install ffmpeg` |

Check you have both:

```sh
python3 --version   # needs 3.11+
ffmpeg -version     # any recent version is fine
```

---

## Install in 60 seconds

```sh
# 1. Go to the project folder
cd /path/to/rgbascii

# 2. Create a virtual environment (keeps everything tidy)
python3 -m venv .venv

# 3. Activate it
#    macOS / Linux (bash/zsh):
source .venv/bin/activate
#    macOS / Linux (fish shell):
source .venv/bin/activate.fish
#    Windows:
.venv\Scripts\activate

# 4. Install rgbascii with audio support
pip install ".[audio]"
```

> **Tip — Using the venv without activating it:**
> You can always call `.venv/bin/rgbascii` (or `.venv\Scripts\rgbascii` on Windows)
> directly without activating the environment.

---

## Quick start

```sh
rgbascii movie.mp4
```

That's it. The video plays in full colour, loops forever, and audio plays through
your speakers. Press **q** to quit.

---

## Render modes

Choose with `--mode <name>`:

| Mode | What it looks like | Best for |
|---|---|---|
| `ascii` (default) | Coloured ASCII characters, luminance-mapped glyphs | General use |
| `rgb` | Identical to `ascii` (alias) | — |
| `grayscale` | Characters + grey tones only | Monochrome look |
| `mono` | Single highlight colour, no per-pixel colour | Stylised / artistic |
| `halfblock` | Block characters (▀) — 2× more vertical detail | Smooth, almost-pixel video |

```sh
rgbascii movie.mp4 --mode halfblock     # smoothest picture
rgbascii movie.mp4 --mode grayscale     # black-and-white
rgbascii movie.mp4 --mode mono --mono-color FF0080   # hot-pink tint
```

---

## All options

### Size & terminal

```
--width N         Render width in terminal columns (auto by default)
--height N        Render height in terminal rows   (auto by default)
--fullscreen      Use the alternate screen buffer — hides your shell history (default)
--no-fullscreen   Render in-place, keeps your shell visible above/below
--aspect F        Vertical squeeze factor (default 0.5 — corrects for tall terminal chars)
```

Most of the time you only need `--width`:

```sh
rgbascii movie.mp4 --width 80          # 80-column render
rgbascii movie.mp4 --width 120 --height 40   # fixed box (letterboxed)
```

### Render mode & character set

```
--mode MODE       ascii | rgb | grayscale | mono | halfblock  (default: ascii)
--charset STR     Custom character ramp or preset name
                  Presets: standard, dense, minimal, blocks
--invert          Flip bright↔dark mapping (bright glyphs on dark pixels)
--sample METHOD   How each cell picks its colour: average | center | weighted
                  (default: average — best colour accuracy)
--color-levels N  Posterise colours to N levels per channel (1–256)
--mono-color HEX  Fixed colour for --mode mono, as RRGGBB hex (default: FFFFFF)
```

```sh
rgbascii movie.mp4 --charset dense             # more glyph detail
rgbascii movie.mp4 --charset blocks            # block art
rgbascii movie.mp4 --charset "@#*+=-. "        # custom ramp
rgbascii movie.mp4 --invert                    # dark-on-light terminal
rgbascii movie.mp4 --color-levels 4            # retro posterised look
```

### Colour

```
--color           Force colour output on (useful if piping to a colour pager)
--no-color        Plain text only — no ANSI colour codes at all
```

### Image adjustment

All values are applied in order: brightness → contrast → saturation → gamma.

```
--brightness F    Add to brightness  (-1.0 to 1.0, default 0)
--contrast F      Multiply contrast  (positive float, default 1)
--saturation F    Colour saturation  (0 = greyscale, 1 = normal, >1 = boosted)
--gamma F         Gamma correction   (default 1 — use <1 to brighten shadows)
```

```sh
rgbascii movie.mp4 --brightness 0.1 --contrast 1.2    # slightly punchy
rgbascii movie.mp4 --saturation 2.0                   # hyper-saturated
rgbascii movie.mp4 --saturation 0 --gamma 0.8         # moody greyscale
```

### Playback

```
--loop            Loop the video forever (default — on by default)
--no-loop         Play once and exit when the video ends
--start S         Start playback at S seconds into the video
--end E           Stop playback at E seconds (must be > --start)
--fps N           Target frame rate (default: use the video's own FPS, 1–240)
--no-audio        Disable audio entirely (video-only clock)
--clock MODE      Master clock source: auto | audio | video  (default: auto)
--buffer-ms MS    Decode-ahead queue in milliseconds (default 120)
--catchup-ms MS   Lag threshold that triggers a hard decoder re-seek (default 350)
```

```sh
rgbascii movie.mp4 --no-loop              # play once then quit
rgbascii movie.mp4 --start 60 --end 120  # play minutes 1–2 only
rgbascii movie.mp4 --no-audio            # silent / video clock only
rgbascii movie.mp4 --fps 15              # slow it down to 15 fps
```

### Misc

```
--frames N        Render exactly N frames then exit (useful for testing)
--debug           Print live FPS, drop counters and a final summary to stderr
--version         Show version and exit
```

---

## Keyboard controls

These work **while the video is playing** (press the key once, no Enter needed):

| Key | Action |
|---|---|
| `Space` or `p` | Pause / resume |
| `q` | Quit |
| `←` | Seek back 5 seconds |
| `→` | Seek forward 5 seconds |
| `+` | Increase cell resolution (finer grid) |
| `-` | Decrease cell resolution (coarser grid) |
| `r` | Restart from `--start` position |

---

## Tips & recipes

**Smoothest picture**

```sh
rgbascii movie.mp4 --mode halfblock --width 120
```

**Watch a clip with a neon-pink tint**

```sh
rgbascii movie.mp4 --mode mono --mono-color FF00CC --width 100
```

**Play only the first 30 seconds, then quit**

```sh
rgbascii movie.mp4 --end 30 --no-loop
```

**Skip the intro and start at 1 minute**

```sh
rgbascii movie.mp4 --start 60
```

**Render without taking over the full screen**

```sh
rgbascii movie.mp4 --no-fullscreen --width 80
```

**Diagnose performance issues**

```sh
rgbascii movie.mp4 --debug 2>stats.log
```

**Ultra-detailed black-and-white**

```sh
rgbascii movie.mp4 --mode grayscale --charset dense --width 200
```

**Render exactly 100 frames to test something**

```sh
rgbascii movie.mp4 --frames 100 --no-loop
```

---

## Troubleshooting

### No audio / silent playback

1. Make sure you installed with audio support:
   ```sh
   pip install ".[audio]"
   ```
2. Check `sounddevice` is installed:
   ```sh
   python -c "import sounddevice; print(sounddevice.__version__)"
   ```
3. Check `ffmpeg` is on your PATH:
   ```sh
   ffmpeg -version
   ```
4. Force video-only mode to rule out audio issues:
   ```sh
   rgbascii movie.mp4 --no-audio
   ```

### Video looks wrong or garbled

- Your terminal may not support **24-bit True Color**. Try `--no-color` or `--mode mono`.
- Try a narrower width so the terminal doesn't wrap:
  ```sh
  rgbascii movie.mp4 --width 80
  ```

### Plays too slowly / too many dropped frames

- Lower the width: `--width 60`
- Use a coarser mode: `--mode ascii` (halfblock is heavier)
- Raise the catchup threshold: `--catchup-ms 500`

### Video freezes after a few seconds

- This was a known bug (now fixed). Make sure you are on the latest version.
- Run with `--debug` to see if frames are being dropped.

### `ffmpeg not found`

Install FFmpeg and make sure it is on your `PATH`:

```sh
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows (with Chocolatey)
choco install ffmpeg
```

### Terminal size issues

The renderer auto-detects your terminal size. If it looks wrong:

```sh
rgbascii movie.mp4 --width 80 --height 24   # force a fixed size
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Normal end (video finished or you pressed `q`) |
| `1` | Runtime error (bad file, missing ffmpeg, etc.) |
| `2` | Usage error (wrong arguments) |
| `130` | Interrupted with Ctrl-C |

---

## Development

```sh
pip install -e ".[dev]"   # editable install with test deps
pytest                    # run all 140 tests
python benchmarks/bench_render.py   # per-stage render timings
```

---

## License

MIT — see [`LICENSE`](LICENSE).