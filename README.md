# Go Board Screenshot → SGF Converter

Convert a screenshot of a 19×19 Go (Baduk / Weiqi) board into a standard [SGF](https://www.red-bean.com/sgf/) file and optionally launch [KaTrain](https://github.com/sanderland/katrain) or [KataGo](https://github.com/lightvector/KataGo) for analysis — all in one click.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Automatic board detection** — finds the 19×19 grid via Hough line detection + uniform grid fitting, even with coordinate labels and UI elements around the board
- **Adaptive stone recognition** — classifies each intersection as black, white, or empty using the board's own background as a reference (works across different board colours and lighting)
- **Clipboard paste** — press `Ctrl+V` to load a screenshot directly from the clipboard
- **SGF output** — generates a valid SGF file with `AB[]` / `AW[]` setup nodes and `PL[]` for player to play
- **One-click analysis** — automatically opens the generated SGF in KaTrain or KataGo
- **Persistent settings** — remembers your engine path and output directory between sessions
- **Portable executable** — can be compiled into a single standalone binary for Windows, Linux, and macOS

## How It Works

1. **Grid detection** — Canny edge detection → HoughLines → classify lines as horizontal/vertical → deduplicate → estimate uniform spacing → fit a 19-line grid by minimising squared error against detected lines
2. **Board stats** — sample brightness and saturation at midpoints between intersections (where stones are unlikely) to characterise the board background
3. **Stone classification** — for each of the 361 intersections, extract a patch and classify based on adaptive brightness/saturation thresholds relative to the board
4. **Circle refinement** — a HoughCircles pass catches any stones missed by the grid-based approach
5. **SGF generation** — map the 19×19 array to SGF coordinates (`aa`–`ss`) and write `AB[]`/`AW[]` properties

## Installation

### Pre-built Releases

Download the latest compiled binary for your platform from the [**Releases**](https://github.com/BitWss/PhotoToSgf/releases/tag/v1.0.0) page — no Python installation required.

| Platform | File |
|----------|------|
| Windows  | `GoScannerSGF.exe` |
| Linux    | `GoScannerSGF` |
| macOS    | `GoScannerSGF` |

### Run from Source

Install Python 3.10+, then install the Python dependencies:

```bash
pip install opencv-python numpy Pillow
```

**Linux** — `tkinter` and clipboard support are not bundled and must be installed separately:

```bash
# Debian / Ubuntu
sudo apt install python3-tk xclip

# Fedora / RHEL
sudo dnf install python3-tkinter xclip

# Arch Linux
sudo pacman -S python-pillow tk xclip
```

**macOS** — `tkinter` is not included with Homebrew Python:

```bash
# Homebrew Python
brew install python-tk

# Alternatively, use the official python.org installer which bundles tkinter
```

Then launch the app on any platform:

```bash
python go_board_to_sgf.py
```

## Build Guide

Build a standalone binary using [PyInstaller](https://pyinstaller.org). Install it first:

```bash
pip install pyinstaller
```

### Windows

```bash
pyinstaller --onefile --windowed --name GoScannerSGF go_board_to_sgf.py
```

Output: `dist/GoScannerSGF.exe`

### Linux

```bash
pyinstaller --onefile --name GoScannerSGF go_board_to_sgf.py
```

Output: `dist/GoScannerSGF`

Make it executable if needed:

```bash
chmod +x dist/GoScannerSGF
```

### macOS

```bash
pyinstaller --onefile --windowed --name GoScannerSGF go_board_to_sgf.py
```

Output: `dist/GoScannerSGF`

To allow macOS to run the unsigned binary, you may need to clear the quarantine flag:

```bash
xattr -d com.apple.quarantine dist/GoScannerSGF
```

---

> All binaries are approximately 60–80 MB. No Python installation is needed on the target machine. Build on the target OS — PyInstaller does not cross-compile.

## Usage

1. Take a screenshot of a Go board (or copy it to your clipboard)
2. Launch the app and either **browse** for the image file or press **Ctrl+V** to paste
3. Choose an output directory for the SGF file
4. (Optional) Set the path to your KaTrain or KataGo executable — this is saved automatically for next time
5. Click **Convert to SGF** or **Convert & Analyze**

The generated `analyzed_board.sgf` can be opened in any SGF-compatible application.

## Supported Sources

Tested with screenshots from:

- [FoxWQ (野狐围棋)](https://www.foxwq.com/)
- [OGS](https://online-go.com/)
- [KGS](https://www.gokgs.com/)

Should work with any Go board screenshot that has a visible grid and clearly distinguishable black/white stones on a wood, green, or similarly coloured background.

## SGF Output Format

The tool generates a single SGF node with setup properties (no move history, since a screenshot can't provide that):

```sgf
(;SZ[19]PL[B]AB[dd][dp][pp]AW[pd][qf])
```

- `SZ[19]` — board size
- `PL[B]` or `PL[W]` — player to play (selectable in the GUI)
- `AB[...]` — add black stones
- `AW[...]` — add white stones

## Requirements

- Python 3.10+
- `opencv-python` (or `opencv-python-headless` for non-GUI use)
- `numpy`
- `Pillow` (for clipboard paste support)
- `tkinter` (bundled with Python on Windows and python.org macOS installer; install separately on Linux and Homebrew macOS)
- `xclip` (Linux only, for clipboard paste)

## Related Projects

- [Kifu Snap](https://www.remi-coulom.fr/kifu-snap/) — automatic Go board image recognition by Rémi Coulom
- [LizGoban SGF from Image](https://kaorahi.github.io/lizgoban/src/sgf_from_image/sgf_from_image.html) — semi-automatic browser-based tool
- [GoScanner](https://github.com/JoeHowarth/GoScanner) — CNN-based Go board scanner
- [GOimage2SGF](https://github.com/nickhuang99/GOimage2SGF) — C++ command-line tool with webcam support
- [Imago](https://github.com/tomasmcz/imago) — Go board image recognition by Tomáš Musil

## License

MIT
