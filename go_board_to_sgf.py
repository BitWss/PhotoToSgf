"""
Go Board Screenshot → SGF Converter  v2.0
==========================================
Detects a 19×19 Go board from a screenshot, identifies Black/White stones,
generates a standard SGF file, and optionally launches KaTrain or KataGo
for analysis.

Key algorithms:
 • Grid detection via HoughLines + uniform grid fitting (robust to missing lines)
 • Adaptive stone classification using board background as reference
 • HoughCircles refinement pass
 • Handles screenshots with coordinate labels / UI chrome
 • Output directory chooser in the GUI

Dependencies: opencv-python, numpy
Optional: sgfmill (falls back to manual SGF formatting)
GUI: Tkinter (bundled with Python on Windows)
"""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
import numpy as np
import os
import subprocess
import threading
import math
import json
import traceback
import tempfile

try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------------------------------------------------------------------------
# SGF generation
# ---------------------------------------------------------------------------

def board_to_sgf_string(board: list[list[int]], player_to_play: str = "B") -> str:
    """
    Convert a 19×19 board array into a valid SGF string.
    board[row][col]: 0 = empty, 1 = black, 2 = white.
    Row 0 = top of the board (line 19), row 18 = bottom (line 1).
    Col 0 = column A (SGF 'a'), col 18 = column T (SGF 's').
    """
    ab_points = []
    aw_points = []
    for row in range(19):
        for col in range(19):
            coord = chr(ord('a') + col) + chr(ord('a') + row)
            if board[row][col] == 1:
                ab_points.append(f"[{coord}]")
            elif board[row][col] == 2:
                aw_points.append(f"[{coord}]")

    sgf = f"(;SZ[19]PL[{player_to_play}]"
    if ab_points:
        sgf += "AB" + "".join(ab_points)
    if aw_points:
        sgf += "AW" + "".join(aw_points)
    sgf += ")"
    return sgf


def save_sgf(board: list[list[int]], output_path: str,
             player_to_play: str = "B") -> str:
    """Write the SGF file and return its path."""
    sgf = board_to_sgf_string(board, player_to_play)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(sgf)
    return output_path


# ---------------------------------------------------------------------------
# Grid detection – Hough lines + uniform grid fitting
# ---------------------------------------------------------------------------

def _fit_uniform_grid(positions: list[float], n_lines: int = 19) -> list[float]:
    """
    Given noisy line-position detections, fit a perfectly uniform grid
    of *n_lines* evenly-spaced positions.

    Algorithm:
      1. Deduplicate nearby detections (merge within 10 px).
      2. Estimate the fundamental spacing from the median of "good" gaps.
      3. Search for the start offset that minimises squared error against
         all detected lines.
    """
    if not positions:
        return []

    positions = sorted(positions)

    # Deduplicate: merge positions within 10 px of each other
    deduped = [positions[0]]
    for p in positions[1:]:
        if p - deduped[-1] > 10:
            deduped.append(p)
        else:
            deduped[-1] = (deduped[-1] + p) / 2

    if len(deduped) < 5:
        return []

    # Estimate spacing from the median of "single-cell" gaps
    gaps = [deduped[i + 1] - deduped[i] for i in range(len(deduped) - 1)]
    median_gap = float(np.median(gaps))
    good_gaps = [g for g in gaps if 0.5 * median_gap < g < 1.5 * median_gap]
    spacing = float(np.median(good_gaps)) if good_gaps else \
              (deduped[-1] - deduped[0]) / (n_lines - 1)

    # Centre-based initial estimate
    total_span = spacing * (n_lines - 1)
    center = (deduped[0] + deduped[-1]) / 2
    start_guess = center - total_span / 2

    # Fine-tune start by minimising sum-of-squared distances
    best_start = start_guess
    best_error = float("inf")
    deduped_arr = np.array(deduped)
    for offset in np.arange(-spacing, spacing, 1.0):
        trial = start_guess + offset
        grid = np.array([trial + i * spacing for i in range(n_lines)])
        # Vectorised: for each detected line, find min distance to any grid line
        dists = np.abs(deduped_arr[:, None] - grid[None, :])
        error = float(np.sum(np.min(dists, axis=1) ** 2))
        if error < best_error:
            best_error = error
            best_start = trial

    return [best_start + i * spacing for i in range(n_lines)]


def _detect_grid(gray: np.ndarray):
    """
    Detect the 19×19 grid on a Go board image.
    Returns (rows_y, cols_x) – two lists of 19 pixel coordinates each,
    or None if the grid cannot be reliably detected.
    """
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=max(min(h, w) // 5, 80))
    if lines is None:
        return None

    h_positions: list[float] = []
    v_positions: list[float] = []
    for rho, theta in lines[:, 0]:
        angle = np.degrees(theta)
        if abs(angle - 90) < 10:           # horizontal
            y = rho / np.sin(theta) if np.sin(theta) != 0 else rho
            h_positions.append(y)
        elif angle < 10 or angle > 170:     # vertical
            x = rho / np.cos(theta) if np.cos(theta) != 0 else rho
            v_positions.append(abs(x))

    if len(h_positions) < 10 or len(v_positions) < 10:
        return None

    rows_y = _fit_uniform_grid(h_positions, 19)
    cols_x = _fit_uniform_grid(v_positions, 19)

    if len(rows_y) != 19 or len(cols_x) != 19:
        return None

    return rows_y, cols_x


# ---------------------------------------------------------------------------
# Fallback board isolation (contour / colour)
# ---------------------------------------------------------------------------

def _find_board_contour(gray: np.ndarray):
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edges = cv2.Canny(blurred, 30, 120)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    for cnt in contours[:10]:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            rect = cv2.boundingRect(approx)
            ratio = rect[2] / rect[3] if rect[3] > 0 else 0
            if 0.7 < ratio < 1.3:
                return approx
    return None


def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
    d = np.diff(pts, axis=1)
    rect[1], rect[3] = pts[np.argmin(d)], pts[np.argmax(d)]
    return rect


def _warp_board(img, contour, size=760):
    pts = contour.reshape(4, 2).astype("float32")
    ordered = _order_points(pts)
    dst = np.float32([[0, 0], [size, 0], [size, size], [0, size]])
    M = cv2.getPerspectiveTransform(ordered, dst)
    return cv2.warpPerspective(img, M, (size, size))


def _crop_board_by_colour(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([10, 30, 100]), np.array([35, 255, 255]))
    mask2 = cv2.inRange(hsv, np.array([35, 30, 80]), np.array([85, 255, 255]))
    mask = cv2.bitwise_or(mask1, mask2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        x, y, bw, bh = cv2.boundingRect(max(contours, key=cv2.contourArea))
        side = max(bw, bh)
        cx, cy = x + bw // 2, y + bh // 2
        x1, y1 = max(cx - side // 2, 0), max(cy - side // 2, 0)
        x2, y2 = min(x1 + side, img.shape[1]), min(y1 + side, img.shape[0])
        return img[y1:y2, x1:x2]
    return img


# ---------------------------------------------------------------------------
# Stone classification – adaptive thresholds
# ---------------------------------------------------------------------------

def _estimate_board_stats(gray, hsv, rows_y, cols_x):
    """
    Sample brightness and saturation at the midpoints between intersections
    (where stones are unlikely) to characterise the board background.
    """
    h, w = gray.shape[:2]
    samples_b, samples_s = [], []
    for i in range(min(18, len(rows_y) - 1)):
        for j in range(min(18, len(cols_x) - 1)):
            my = int((rows_y[i] + rows_y[i + 1]) / 2)
            mx = int((cols_x[j] + cols_x[j + 1]) / 2)
            if 0 <= my < h and 0 <= mx < w:
                samples_b.append(float(gray[my, mx]))
                samples_s.append(float(hsv[my, mx, 1]))
    if not samples_b:
        return 140.0, 80.0
    return float(np.median(samples_b)), float(np.median(samples_s))


def _classify_stone(mean_b, std_b, mean_sat,
                    board_brightness, board_saturation) -> int:
    """0 = empty, 1 = black, 2 = white."""
    dark_thresh = board_brightness * 0.48
    bright_thresh = board_brightness * 1.15
    sat_thresh = board_saturation * 0.55

    if mean_b < dark_thresh:
        return 1
    if mean_b > bright_thresh and mean_sat < sat_thresh and std_b < 45:
        return 2
    if mean_b < board_brightness * 0.55 and std_b < 50:
        return 1
    if (mean_b > board_brightness * 1.05
            and mean_sat < board_saturation * 0.7
            and std_b < 55):
        return 2
    return 0


# ---------------------------------------------------------------------------
# Full detection pipeline
# ---------------------------------------------------------------------------

def detect_board_and_stones(img: np.ndarray) -> list[list[int]]:
    """
    Main entry point.  Returns a 19×19 list (0 = empty, 1 = black, 2 = white).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    result = _detect_grid(gray)

    working_img = img
    if result is not None:
        rows_y, cols_x = result
    else:
        # Fallback: isolate the board region, then retry grid detection
        contour = _find_board_contour(gray)
        if contour is not None:
            working_img = _warp_board(img, contour, 760)
        else:
            working_img = _crop_board_by_colour(img)
            working_img = cv2.resize(working_img, (760, 760))

        gray2 = cv2.cvtColor(working_img, cv2.COLOR_BGR2GRAY)
        result = _detect_grid(gray2)
        if result is not None:
            rows_y, cols_x = result
        else:
            # Last resort: assume uniform grid with small margin
            h2, w2 = working_img.shape[:2]
            m = 0.05
            rows_y = [m * h2 + i * (h2 * (1 - 2 * m)) / 18 for i in range(19)]
            cols_x = [m * w2 + i * (w2 * (1 - 2 * m)) / 18 for i in range(19)]

    gray_w = cv2.cvtColor(working_img, cv2.COLOR_BGR2GRAY)
    hsv_w = cv2.cvtColor(working_img, cv2.COLOR_BGR2HSV)
    board_b, board_s = _estimate_board_stats(gray_w, hsv_w, rows_y, cols_x)

    spacing = min(
        (rows_y[-1] - rows_y[0]) / 18,
        (cols_x[-1] - cols_x[0]) / 18,
    )
    radius = int(spacing * 0.35)

    board: list[list[int]] = []
    for row in range(19):
        row_data: list[int] = []
        for col in range(19):
            cy = int(round(rows_y[row]))
            cx = int(round(cols_x[col]))
            y1, y2 = max(cy - radius, 0), min(cy + radius + 1, gray_w.shape[0])
            x1, x2 = max(cx - radius, 0), min(cx + radius + 1, gray_w.shape[1])
            g = gray_w[y1:y2, x1:x2]
            h_p = hsv_w[y1:y2, x1:x2]
            stone = _classify_stone(
                float(np.mean(g)), float(np.std(g)),
                float(np.mean(h_p[:, :, 1])),
                board_b, board_s,
            )
            row_data.append(stone)
        board.append(row_data)

    # Refinement pass with HoughCircles
    board = _refine_circles(working_img, gray_w, hsv_w, board,
                            rows_y, cols_x, spacing, board_b, board_s)
    return board


def _refine_circles(img, gray, hsv, board, rows_y, cols_x,
                    spacing, board_b, board_s):
    blurred = cv2.medianBlur(gray, 5)
    min_r, max_r = int(spacing * 0.25), int(spacing * 0.55)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=int(spacing * 0.7),
        param1=50, param2=30,
        minRadius=min_r, maxRadius=max_r,
    )
    if circles is None:
        return board

    # Pre-compute grid arrays for fast nearest-intersection lookup
    gy = np.array(rows_y)
    gx = np.array(cols_x)

    for cx, cy, r in np.round(circles[0]).astype(int):
        # Vectorised nearest intersection
        best_c = int(np.argmin(np.abs(gx - cx)))
        best_r = int(np.argmin(np.abs(gy - cy)))
        best_d = math.hypot(cx - gx[best_c], cy - gy[best_r])
        if best_d < spacing * 0.5:
            cr = int(r * 0.7)
            y1, y2 = max(cy - cr, 0), min(cy + cr + 1, gray.shape[0])
            x1, x2 = max(cx - cr, 0), min(cx + cr + 1, gray.shape[1])
            g = gray[y1:y2, x1:x2]
            h_p = hsv[y1:y2, x1:x2]
            s = _classify_stone(
                float(np.mean(g)), float(np.std(g)),
                float(np.mean(h_p[:, :, 1])),
                board_b, board_s,
            )
            if s != 0:
                board[best_r][best_c] = s
    return board


# ---------------------------------------------------------------------------
# High-level pipeline
# ---------------------------------------------------------------------------

def process_image(image_path: str, output_path: str,
                  player_to_play: str = "B") -> str:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    board = detect_board_and_stones(img)
    save_sgf(board, output_path, player_to_play)
    return output_path


# ---------------------------------------------------------------------------
# Launch KaTrain / KataGo
# ---------------------------------------------------------------------------

def launch_engine(engine_path: str, sgf_path: str) -> None:
    if not os.path.isfile(engine_path):
        raise FileNotFoundError(f"Engine not found: {engine_path}")
    if not os.path.isfile(sgf_path):
        raise FileNotFoundError(f"SGF file not found: {sgf_path}")
    subprocess.Popen([engine_path, os.path.abspath(sgf_path)])


# ---------------------------------------------------------------------------
# Persistent config  (remembers engine path & output directory)
# ---------------------------------------------------------------------------

def _config_path() -> str:
    """Return path to the JSON config file next to the executable / script."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "go_scanner_config.json")


def _load_config() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass  # non-critical


# ---------------------------------------------------------------------------
# Tkinter GUI
# ---------------------------------------------------------------------------

class GoScannerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Go Board Screenshot → SGF  v2")
        self.root.resizable(False, False)
        self.root.geometry("580x420")

        cfg = _load_config()

        self.image_path = tk.StringVar()
        self.engine_path = tk.StringVar(value=cfg.get("engine_path", ""))
        self.output_dir = tk.StringVar(
            value=cfg.get("output_dir", os.path.expanduser("~")))
        self.player_to_play = tk.StringVar(value="B")
        self.status_text = tk.StringVar(
            value="Select a screenshot or paste from clipboard (Ctrl+V).")
        self._clipboard_file: str | None = None   # temp file for pasted images

        self._build_ui()
        self.root.bind("<Control-v>", self._paste_clipboard)

    def _build_ui(self):
        pad = {"padx": 12, "pady": 5}

        # --- Image selection ---
        f1 = ttk.LabelFrame(self.root, text="Screenshot")
        f1.pack(fill="x", **pad)
        ttk.Entry(f1, textvariable=self.image_path, width=52).pack(
            side="left", padx=(8, 4), pady=8)
        ttk.Button(f1, text="Browse…", command=self._pick_image).pack(
            side="left", padx=(0, 8), pady=8)

        # --- Output directory ---
        f2 = ttk.LabelFrame(self.root, text="Output directory")
        f2.pack(fill="x", **pad)
        ttk.Entry(f2, textvariable=self.output_dir, width=52).pack(
            side="left", padx=(8, 4), pady=8)
        ttk.Button(f2, text="Browse…", command=self._pick_outdir).pack(
            side="left", padx=(0, 8), pady=8)

        # --- Engine selection ---
        f3 = ttk.LabelFrame(self.root, text="KaTrain / KataGo executable (optional)")
        f3.pack(fill="x", **pad)
        ttk.Entry(f3, textvariable=self.engine_path, width=52).pack(
            side="left", padx=(8, 4), pady=8)
        ttk.Button(f3, text="Browse…", command=self._pick_engine).pack(
            side="left", padx=(0, 8), pady=8)

        # --- Options ---
        fo = ttk.Frame(self.root)
        fo.pack(fill="x", **pad)
        ttk.Label(fo, text="Player to play:").pack(side="left", padx=(0, 4))
        ttk.Radiobutton(fo, text="Black", variable=self.player_to_play,
                        value="B").pack(side="left")
        ttk.Radiobutton(fo, text="White", variable=self.player_to_play,
                        value="W").pack(side="left", padx=(8, 0))

        # --- Action buttons ---
        fb = ttk.Frame(self.root)
        fb.pack(fill="x", **pad)
        self.btn_convert = ttk.Button(fb, text="Convert to SGF",
                                      command=self._run_conversion)
        self.btn_convert.pack(side="left", padx=4)
        self.btn_analyze = ttk.Button(fb, text="Convert & Analyze",
                                      command=self._run_and_analyze)
        self.btn_analyze.pack(side="left", padx=4)

        # --- Status ---
        fs = ttk.LabelFrame(self.root, text="Status")
        fs.pack(fill="x", **pad)
        ttk.Label(fs, textvariable=self.status_text, wraplength=540).pack(
            padx=8, pady=8)

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=12, pady=(0, 8))

    # -- File dialogs / clipboard -------------------------------------

    def _pick_image(self):
        p = filedialog.askopenfilename(
            title="Select Go Board Screenshot",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                       ("All", "*.*")])
        if p:
            self.image_path.set(p)
            self.status_text.set(f"Image: {os.path.basename(p)}")

    def _paste_clipboard(self, event=None):
        """Grab an image from the system clipboard (Ctrl+V)."""
        if not HAS_PIL:
            self.status_text.set("Clipboard paste requires Pillow: pip install Pillow")
            return
        try:
            clip = ImageGrab.grabclipboard()
        except Exception:
            clip = None
        if clip is None:
            self.status_text.set("No image found in clipboard.")
            return
        # Save to a temp file so the rest of the pipeline can use cv2.imread
        tmp = os.path.join(tempfile.gettempdir(), "go_scanner_clipboard.png")
        clip.save(tmp, "PNG")
        self._clipboard_file = tmp
        self.image_path.set(tmp)
        self.status_text.set("Pasted image from clipboard.")

    def _pick_outdir(self):
        p = filedialog.askdirectory(title="Select Output Directory")
        if p:
            self.output_dir.set(p)
            self._persist()

    def _pick_engine(self):
        p = filedialog.askopenfilename(
            title="Select KaTrain / KataGo executable",
            filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if p:
            self.engine_path.set(p)
            self._persist()

    # -- Conversion (threaded) -----------------------------------------

    def _persist(self):
        """Save current engine path and output dir to config file."""
        _save_config({
            "engine_path": self.engine_path.get().strip(),
            "output_dir": self.output_dir.get().strip(),
        })

    def _set_busy(self, busy):
        st = "disabled" if busy else "normal"
        self.btn_convert.config(state=st)
        self.btn_analyze.config(state=st)
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()

    def _run_conversion(self, launch=False):
        img = self.image_path.get().strip()
        if not img or not os.path.isfile(img):
            messagebox.showerror("Error", "Select a valid image file.")
            return
        od = self.output_dir.get().strip()
        if not od or not os.path.isdir(od):
            messagebox.showerror("Error", "Select a valid output directory.")
            return

        self._set_busy(True)
        self.status_text.set("Processing…")
        out = os.path.join(od, "analyzed_board.sgf")
        ptp = self.player_to_play.get()

        def worker():
            try:
                sgf = process_image(img, out, ptp)
                self.root.after(0, lambda: self._done(sgf, launch))
            except Exception as e:
                err = traceback.format_exc()
                self.root.after(0, lambda: self._error(str(e) + "\n" + err))

        threading.Thread(target=worker, daemon=True).start()

    def _run_and_analyze(self):
        eng = self.engine_path.get().strip()
        if not eng or not os.path.isfile(eng):
            messagebox.showerror("Error", "Set a valid engine executable.")
            return
        self._run_conversion(launch=True)

    def _done(self, sgf_path, launch):
        self._set_busy(False)
        self.status_text.set(f"Done — saved to {sgf_path}")
        if launch:
            try:
                launch_engine(self.engine_path.get().strip(), sgf_path)
                self.status_text.set("Engine launched.")
            except Exception as e:
                messagebox.showerror("Engine Error", str(e))

    def _error(self, msg):
        self._set_busy(False)
        self.status_text.set(f"Error: {msg}")
        messagebox.showerror("Error", msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    GoScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
