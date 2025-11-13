#!/usr/bin/env python3
"""
plot_lamp_filepicker.py

Opens a file-picker dialog so you can choose a .dat (or other) file.
Reads the selected TCD1304-style two-column file (pixel, ADC), estimates
ADC_dark from dummy pixels, computes Ipixel = ADC_dark - ADC, creates an
interpolated curve (uses scipy if available, otherwise numpy.interp fallback),
and writes all outputs into a new folder next to the selected file.

Output folder name (created next to the .dat file):
    <original_filename_stem>_<creation-timestamp>

The timestamp is the file system creation time of the selected file, formatted
as YYYYMMDD_HHMMSS so it is safe in filenames.

Files created inside that folder:
  - <prefix>_Ipixel.csv                    (pixel, ADC, Ipixel)
  - <prefix>_interpolated_sample.csv      (high-res sampled regression)
  - <prefix>_plot.png                     (ADC + Ipixel plot with regression overlay)
  - <prefix>_interpolator.pkl             (pickled interpolator object, optional)

Usage:
  - Double-click or run from CMD:
      python plot_lamp_filepicker.py
    A file dialog will open; pick your lamp.dat (or any .dat file).

  - Or run and pass a path to skip the dialog:
      python plot_lamp_filepicker.py "C:\path\to\lamp.dat"

Notes:
  - If you prefer not to have a GUI, pass the file path as the first argument.
  - Be careful when unpickling .pkl files from untrusted sources.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import os
import csv
import pickle
import numpy as np
import matplotlib
matplotlib.use("Agg")   # safe backend for non-interactive use
import matplotlib.pyplot as plt
from datetime import datetime

def choose_file_with_dialog(initialdir: str | None = None) -> Path | None:
    try:
        # Use tkinter filedialog to open a native file selection dialog
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    # On Windows the dialog will be a native explorer-file dialog
    filetypes = [("DAT files", "*.dat"), ("All files", "*.*")]
    filename = filedialog.askopenfilename(title="Select .dat file", initialdir=initialdir or ".", filetypes=filetypes)
    root.update()
    root.destroy()
    if not filename:
        return None
    return Path(filename).expanduser().resolve()

def read_file_lines(filename: str):
    encodings = ["utf-8", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            with open(filename, "r", encoding=enc) as f:
                lines = f.readlines()
            print(f"Opened file using encoding: {enc}")
            return lines
        except UnicodeDecodeError:
            continue
        except Exception as e:
            # other I/O error -> raise
            raise
    # fallback: binary decode with replacement
    with open(filename, "rb") as f:
        raw = f.read()
    lines = raw.decode("utf-8", errors="replace").splitlines()
    print("Opened file via binary fallback, decoded with errors='replace'.")
    return lines

def parse_lines_to_arrays(lines):
    pixels = []
    adcs = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        try:
            p = int(parts[0])
            a = float(parts[1])
        except Exception:
            try:
                p = int(''.join(ch for ch in parts[0] if (ch.isdigit() or ch == '-')))
                a = float(''.join(ch for ch in parts[1] if (ch.isdigit() or ch in ".-eE")))
            except Exception:
                continue
        pixels.append(p)
        adcs.append(a)
    if not pixels:
        raise ValueError("No valid pixel/ADC pairs found in file.")
    return np.array(pixels, dtype=int), np.array(adcs, dtype=float)

def estimate_dark(pixels: np.ndarray, adcs: np.ndarray, method: str = "median"):
    mask = ((pixels >= 1) & (pixels <= 32)) | ((pixels >= 3679) & (pixels <= 3694))
    dark_vals = adcs[mask]
    if dark_vals.size == 0:
        n = pixels.size
        if n >= 64:
            dark_vals = np.concatenate((adcs[:32], adcs[-32:]))
        else:
            dark_vals = adcs[:max(1, n//10)]
    if method == "median":
        return float(np.median(dark_vals)), dark_vals
    else:
        return float(np.mean(dark_vals)), dark_vals

def make_interpolator(pixels: np.ndarray, intensities: np.ndarray, method: str = "spline", smooth: float = 0.2):
    """Create an interpolator. `smooth` increases smoothing when using spline (larger -> smoother).

    Returns (callable, description)
    """
    try:
        if method == "spline":
            from scipy.interpolate import UnivariateSpline
            # stronger smoothing by default: scale factor (user-controlled)
            s = max(0.0, len(pixels) * np.var(intensities) * float(smooth))
            spline = UnivariateSpline(pixels, intensities, s=s)
            return spline, f"UnivariateSpline(s={s:.3g})"
        else:
            from scipy.interpolate import interp1d
            kind = "cubic" if method == "cubic" else "linear"
            f = interp1d(pixels, intensities, kind=kind, bounds_error=False, fill_value="extrapolate")
            return f, f"interp1d({kind})"
    except Exception:
        def lininterp(x):
            return np.interp(x, pixels, intensities)
        return lininterp, "numpy.interp(linear,fallback)"

def save_pixel_csv(pixels: np.ndarray, adcs: np.ndarray, intensities: np.ndarray, out_csv: Path):
    header = ["pixel", "ADC", "Ipixel"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for p, a, i in zip(pixels, adcs, intensities):
            w.writerow([int(p), float(a), float(i)])

def format_ctime_for_name(path: Path) -> str:
    # Use filesystem creation time when available
    try:
        ctime = path.stat().st_ctime
    except Exception:
        ctime = os.path.getctime(str(path))
    dt = datetime.fromtimestamp(ctime)
    return dt.strftime("%Y%m%d_%H%M%S")

def main():
    parser = argparse.ArgumentParser(description="Open a .dat file via dialog and produce intensity + regression outputs in a new timestamped folder.")
    parser.add_argument("infile", nargs="?", default=None, help="optional path to .dat file (if omitted, a file dialog will open)")
    parser.add_argument("--interp", choices=["spline","cubic","linear"], default="spline", help="regression method for overlay and sampled CSV")
    parser.add_argument("--dark-method", choices=["median","mean"], default="median", help="how to estimate ADC_dark")
    parser.add_argument("--samples", type=int, default=10000, help="number of points to sample the interpolated function")
    parser.add_argument("--smooth", type=float, default=0.2, help="smoothing multiplier for spline (larger -> smoother). Default 0.2")
    # Default smooths: keep only the weaker values (remove 0.1 and 0.2 as requested)
    parser.add_argument("--smooths", type=str, default="0.01,0.02,0.05", help="comma-separated list of smoothing multipliers to plot multiple regressions (e.g. '0.01,0.02,0.05')")
    parser.add_argument("--linewidth", type=float, default=0.6, help="default line width for PNG output (thin lines)")
    args = parser.parse_args()

    infile_path: Path | None = None
    if args.infile:
        infile_path = Path(args.infile).expanduser().resolve()
        if not infile_path.is_file():
            print(f"Error: provided infile not found: {infile_path}", file=sys.stderr)
            sys.exit(2)
    else:
        chosen = choose_file_with_dialog()
        if chosen is None:
            # If dialog isn't available or user canceled, ask for path fallback
            if args.infile:
                infile_path = Path(args.infile).expanduser().resolve()
            else:
                p = input("No file chosen. Enter the path to the .dat file (or press Enter to quit): ").strip()
                if not p:
                    print("No file provided. Exiting.")
                    sys.exit(1)
                infile_path = Path(p).expanduser().resolve()
        else:
            infile_path = chosen

    if not infile_path or not infile_path.is_file():
        print(f"Input file not found: {infile_path}", file=sys.stderr)
        sys.exit(2)

    # Determine creation timestamp of the original file for folder name
    timestamp_str = format_ctime_for_name(infile_path)
    out_dir = infile_path.parent / f"{infile_path.stem}_{timestamp_str}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = infile_path.stem

    print(f"Selected file: {infile_path}")
    print(f"Outputs will be written to: {out_dir}")

    # Read and parse
    lines = read_file_lines(str(infile_path))
    pixels, adcs = parse_lines_to_arrays(lines)
    print(f"Read {pixels.size} samples (pixel range {pixels.min()}..{pixels.max()})")

    adc_dark, dark_values = estimate_dark(pixels, adcs, method=args.dark_method)
    print(f"Estimated ADC_dark ({args.dark_method}) = {adc_dark:.3f} from {dark_values.size} dummy pixels")
    intensities = adc_dark - adcs

    # Save per-pixel CSV
    out_csv = out_dir / f"{out_prefix}_Ipixel.csv"
    save_pixel_csv(pixels, adcs, intensities, out_csv)
    print(f"Wrote per-pixel CSV -> {out_csv}")

    # Make interpolator and sample
    # Prepare sampling grid
    xs = np.linspace(pixels.min(), pixels.max(), max(1000, args.samples))

    # Parse multi-smoothing values for plotting several regression strengths
    try:
        smooth_values = [float(s.strip()) for s in str(args.smooths).split(",") if s.strip()]
    except Exception:
        smooth_values = [args.smooth]

    interp_results = []
    for s_val in smooth_values:
        interp_fn_i, interp_kind_i = make_interpolator(pixels, intensities, method=args.interp, smooth=s_val)
        try:
            ys_i = interp_fn_i(xs)
            ys_i = np.asarray(ys_i, dtype=float)
        except Exception:
            ys_i = np.interp(xs, pixels, intensities)
            interp_kind_i = "numpy.interp(fallback)"
        interp_results.append((s_val, interp_kind_i, ys_i))

    # Plot: raw ADC (top), flipped Ipixel (middle), and interpolated/smoothed (bottom)
    fig, (ax0, ax1, ax2) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    lw = float(args.linewidth)
    ax0.plot(pixels, adcs, color="tab:blue", lw=lw, label="ADC (raw)")
    ax0.axhline(adc_dark, color="tab:orange", ls="--", lw=lw, label=f"ADC_dark={adc_dark:.2f}")
    ax0.set_ylabel("ADC counts")
    ax0.legend(fontsize="small")
    ax0.grid(True, alpha=0.3)

    # Middle: flipped (upside-down) so peaks become troughs
    # Use max-based inversion to keep signal in the same positive range
    y_flipped = np.max(intensities) - intensities
    # Make the flipped trace more visually distinct: green, slightly thicker
    ax1.plot(pixels, y_flipped, color="green", lw=max(0.8, lw * 1.2), label="Ipixel (flipped)")
    ax1.set_ylabel("Flipped Ipixel")
    # Visually invert the y-axis so the panel appears upside-down (peaks downwards)
    ax1.invert_yaxis()
    ax1.legend(fontsize="small")
    ax1.grid(True, alpha=0.3)

    # Bottom: interpolated / smoothed (separate plot). Plot multiple curves with different smoothing strengths.
    # Plot a very faint original Ipixel trace in the regression panel for reference
    orig_on_xs = np.interp(xs, pixels, intensities)
    # Slightly more visible raw trace for reference
    ax2.plot(xs, orig_on_xs, color="gray", lw=0.8, alpha=0.28, label="raw Ipixel (faint)")

    # Use only the requested distinct colors (no green/yellow): blue, red, purple
    palette = ["blue", "red", "purple"]
    colors = [palette[i % len(palette)] for i in range(len(interp_results))]
    import math
    for (s_val, kind, ys_i), col in zip(interp_results, colors):
        # Force s=0.05 to green for emphasis per request (use isclose for safety)
        plot_col = "green" if math.isclose(float(s_val), 0.05, rel_tol=1e-6, abs_tol=1e-9) else col
        ax2.plot(xs, ys_i, color=plot_col, lw=max(0.8, lw), alpha=0.95, label=f"s={s_val} ({kind})")
    ax2.set_xlabel("pixel number")
    ax2.set_ylabel("Ipixel (interpolated)")
    ax2.legend(fontsize="small")
    ax2.grid(True, alpha=0.3)

    # Shade dummy pixel regions if within range
    try:
        pmin, pmax = pixels.min(), pixels.max()
        if pmin <= 32:
            ax0.fill_betweenx(ax0.get_ylim(), 1, 32, color="gray", alpha=0.08)
            ax1.fill_betweenx(ax1.get_ylim(), 1, 32, color="gray", alpha=0.08)
            ax2.fill_betweenx(ax2.get_ylim(), 1, 32, color="gray", alpha=0.08)
        if pmax >= 3679:
            ax0.fill_betweenx(ax0.get_ylim(), 3679, 3694, color="gray", alpha=0.08)
            ax1.fill_betweenx(ax1.get_ylim(), 3679, 3694, color="gray", alpha=0.08)
            ax2.fill_betweenx(ax2.get_ylim(), 3679, 3694, color="gray", alpha=0.08)
    except Exception:
        pass

    pngfile = out_dir / f"{out_prefix}_plot.png"
    plt.tight_layout()
    fig.savefig(str(pngfile), dpi=200)
    plt.close(fig)
    print(f"Saved plot -> {pngfile}")
    print("Done. All generated files are in:", out_dir)

if __name__ == "__main__":
    main()