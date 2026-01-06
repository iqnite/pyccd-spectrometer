#!/usr/bin/env python3
"""
plotgraph.py - A4 PDF Scientific Report Generator
Generates 80s-style scientific report PDFs from TCD1304 spectroscopy data.

Features:
- A4 PDF output with black & white typewriter aesthetic
- Logos: AstroLens (black) + pyspec icon
- Metadata: date, name, ICG/SH period, exposure time, avg count, firmware
- Raw mode graph (pixel vs ADC)
- Spectroscopy mode graph (wavelength vs intensity)
- Calibration table & calibration curve with 4 points
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import os
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime
from PIL import Image
import json

# Import scipy for interpolation
try:
    from scipy.interpolate import UnivariateSpline, interp1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Try to import reportlab for better PDF control (optional)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    A4 = (595.276, 841.890)  # A4 in points


def make_interpolator(x, y, method="spline", smooth=0.001):
    """
    Create an interpolation function for spectral data.
    
    Args:
        x: Array of x-values (pixels)
        y: Array of y-values (intensities)
        method: Interpolation method ('spline', 'linear', 'cubic')
        smooth: Smoothing parameter for spline interpolation (default: 0.001)
    
    Returns:
        (interpolator_function, method_name): Tuple of interpolation function and method used
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    
    # Remove any NaN or inf values
    valid_mask = np.isfinite(x) & np.isfinite(y)
    x = x[valid_mask]
    y = y[valid_mask]
    
    if len(x) < 2:
        raise ValueError("Need at least 2 valid points for interpolation")
    
    if method == "spline" and SCIPY_AVAILABLE:
        try:
            # Use UnivariateSpline with smoothing parameter
            # The 's' parameter controls smoothing: 0 = interpolating, larger = more smoothing
            # Scale by variance of data and number of points for better effect
            data_variance = np.var(y) if len(y) > 1 else 1.0
            s_param = smooth * len(x) * data_variance / 100.0
            interpolator = UnivariateSpline(x, y, s=s_param, k=3)
            return interpolator, "spline"
        except Exception:
            # Fall back to linear interpolation if spline fails
            pass
    
    # Fallback to numpy linear interpolation
    def linear_interp(x_new):
        return np.interp(x_new, x, y)
    
    return linear_interp, "linear"


def choose_file_with_dialog(initialdir: str | None = None) -> Path | None:
    """Open a file dialog to select a .dat file"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    filetypes = [("DAT files", "*.dat"), ("All files", "*.*")]
    filename = filedialog.askopenfilename(
        title="Select .dat file", initialdir=initialdir or ".", filetypes=filetypes
    )
    root.update()
    root.destroy()
    if not filename:
        return None
    return Path(filename).expanduser().resolve()


def read_file_lines(filename: str):
    """Read file with multiple encoding fallbacks"""
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
            raise
    # Fallback: binary with replacement
    with open(filename, "rb") as f:
        raw = f.read()
    lines = raw.decode("utf-8", errors="replace").splitlines()
    print("Opened file via binary fallback.")
    return lines


def parse_metadata(lines):
    """Extract metadata from header comments"""
    metadata = {
        'date': 'N/A',
        'time': 'N/A',
        'sample_name': 'Unknown',
        'sh_period': 'N/A',
        'icg_period': 'N/A',
        'integration_time': 'N/A',
        'firmware_avg': 'N/A',
        'firmware_mclk': 'N/A',
        'average_count': 'N/A',
        'spectroscopy_mode': 'False',
        'calibration_coeffs': None
    }
    
    for line in lines:
        line = line.strip()
        if not line.startswith("#"):
            continue
            
        # Parse date and time
        if "#Date:" in line:
            parts = line.split()
            try:
                date_idx = parts.index("#Date:") + 1
                if date_idx < len(parts):
                    metadata['date'] = parts[date_idx]
                time_idx = next((i for i, p in enumerate(parts) if p == "Time:"), -1)
                if time_idx > 0 and time_idx + 1 < len(parts):
                    metadata['time'] = parts[time_idx + 1]
            except:
                pass
        
        # Parse sample name
        if "#Sample-name:" in line:
            parts = line.split()
            try:
                name_idx = parts.index("#Sample-name:") + 1
                if name_idx < len(parts):
                    metadata['sample_name'] = parts[name_idx]
            except:
                pass
        
        # Parse SH and ICG periods
        if "#SH-period:" in line:
            parts = line.split()
            try:
                sh_idx = parts.index("#SH-period:") + 1
                if sh_idx < len(parts):
                    metadata['sh_period'] = parts[sh_idx]
                icg_idx = next((i for i, p in enumerate(parts) if p == "ICG-period:"), -1)
                if icg_idx > 0 and icg_idx + 1 < len(parts):
                    metadata['icg_period'] = parts[icg_idx + 1]
                int_time_idx = next((i for i, p in enumerate(parts) if p == "time:"), -1)
                if int_time_idx > 0 and int_time_idx + 1 < len(parts):
                    metadata['integration_time'] = parts[int_time_idx + 1]
            except:
                pass
        
        # Parse firmware settings
        if "#Firmware-settings:" in line:
            parts = line.split()
            try:
                avg_idx = next((i for i, p in enumerate(parts) if p == "AVG:"), -1)
                if avg_idx > 0 and avg_idx + 1 < len(parts):
                    metadata['firmware_avg'] = parts[avg_idx + 1]
                mclk_idx = next((i for i, p in enumerate(parts) if p == "MCLK:"), -1)
                if mclk_idx > 0 and mclk_idx + 1 < len(parts):
                    metadata['firmware_mclk'] = parts[mclk_idx + 1]
            except:
                pass
        
        # Parse average count
        if "#Average-count:" in line:
            parts = line.split()
            try:
                count_idx = parts.index("#Average-count:") + 1
                if count_idx < len(parts):
                    metadata['average_count'] = parts[count_idx]
            except:
                pass
        
        # Parse spectroscopy mode
        if "#Spectroscopy-mode:" in line:
            parts = line.split()
            try:
                mode_idx = parts.index("#Spectroscopy-mode:") + 1
                if mode_idx < len(parts):
                    metadata['spectroscopy_mode'] = parts[mode_idx]
            except:
                pass
        
        # Parse calibration coefficients
        if "#Calibration-coefficients:" in line:
            parts = line.split()
            try:
                coeff_idx = parts.index("#Calibration-coefficients:") + 1
                if coeff_idx < len(parts):
                    coeff_str = parts[coeff_idx]
                    metadata['calibration_coeffs'] = [float(c) for c in coeff_str.split(',')]
            except:
                pass
    
    return metadata


def format_time_with_unit(time_str):
    """Format time value with the most convenient unit (µs, ms, or s)"""
    try:
        time_us = float(time_str)
        
        # Choose appropriate unit
        if time_us >= 1000000:  # >= 1 second
            value = time_us / 1000000
            unit = 's'
        elif time_us >= 1000:  # >= 1 millisecond
            value = time_us / 1000
            unit = 'ms'
        else:  # microseconds
            value = time_us
            unit = 'µs'
        
        # Format with appropriate precision
        if value >= 100:
            formatted = f"{value:.1f}"
        elif value >= 10:
            formatted = f"{value:.2f}"
        else:
            formatted = f"{value:.3f}"
        
        return f"{formatted} {unit}"
    except:
        return f"{time_str} µs"  # Fallback to original with µs


def format_time_with_unit(time_str):
    """Format time value with the most convenient unit (µs, ms, or s)"""
    try:
        time_us = float(time_str)
        
        # Choose appropriate unit
        if time_us >= 1000000:  # >= 1 second
            value = time_us / 1000000
            unit = 's'
        elif time_us >= 1000:  # >= 1 millisecond
            value = time_us / 1000
            unit = 'ms'
        else:  # microseconds
            value = time_us
            unit = 'µs'
        
        # Format with appropriate precision
        if value >= 100:
            formatted = f"{value:.1f}"
        elif value >= 10:
            formatted = f"{value:.2f}"
        else:
            formatted = f"{value:.3f}"
        
        return f"{formatted} {unit}"
    except:
        return f"{time_str} µs"  # Fallback to original with µs


def parse_lines_to_arrays(lines):
    """Parse data lines to pixel and ADC arrays"""
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
                p = int("".join(ch for ch in parts[0] if (ch.isdigit() or ch == "-")))
                a = float("".join(ch for ch in parts[1] if (ch.isdigit() or ch in ".-eE")))
            except Exception:
                continue
        pixels.append(p)
        adcs.append(a)
    if not pixels:
        raise ValueError("No valid pixel/ADC pairs found in file.")
    return np.array(pixels, dtype=int), np.array(adcs, dtype=float)


def estimate_dark(pixels: np.ndarray, adcs: np.ndarray, method: str = "median"):
    """Estimate dark/baseline from dummy pixels"""
    mask = ((pixels >= 1) & (pixels <= 32)) | ((pixels >= 3679) & (pixels <= 3694))
    dark_vals = adcs[mask]
    if dark_vals.size == 0:
        n = pixels.size
        if n >= 64:
            dark_vals = np.concatenate((adcs[:32], adcs[-32:]))
        else:
            dark_vals = adcs[:max(1, n // 10)]
    if method == "median":
        return float(np.median(dark_vals)), dark_vals
    else:
        return float(np.mean(dark_vals)), dark_vals


def load_calibration_points():
    """Load calibration points from calibration_params.json"""
    try:
        if os.path.exists("calibration_params.json"):
            with open("calibration_params.json", "r") as f:
                data = json.load(f)
                return data.get("points", [])
    except:
        pass
    # Default 4-point calibration
    return [
        {"pixel": 0, "wavelength": 350.0},
        {"pixel": 1231, "wavelength": 532.0},
        {"pixel": 2462, "wavelength": 700.0},
        {"pixel": 3693, "wavelength": 800.0}
    ]


def apply_calibration(pixels, coeffs=None):
    """Apply polynomial calibration to convert pixels to wavelengths"""
    if coeffs is None:
        # Load from calibration points
        points = load_calibration_points()
        pixel_vals = [p["pixel"] for p in points]
        wavelength_vals = [p["wavelength"] for p in points]
        coeffs = np.polyfit(pixel_vals, wavelength_vals, 3)
    
    polynomial = np.poly1d(coeffs)
    return polynomial(pixels)


def load_and_convert_logo(logo_path, target_height=60, convert_yellow_to_white=False):
    """Load logo and convert to pure black (remove any color)"""
    try:
        img = Image.open(logo_path).convert("RGBA")
        # Convert to grayscale, then to pure black/white
        gray = img.convert("L")
        
        # If we need to convert yellow to white (for pyspec icon)
        if convert_yellow_to_white:
            img_rgb = Image.open(logo_path).convert("RGB")
            pixels_rgb = img_rgb.load()
            gray_pixels = gray.load()
            # Convert yellow/bright colors to white in grayscale
            for y in range(gray.size[1]):
                for x in range(gray.size[0]):
                    r, g, b = pixels_rgb[x, y]
                    # Detect yellow-ish colors (high R and G, low B)
                    if r > 180 and g > 150 and b < 100:
                        gray_pixels[x, y] = 255  # Make it white
        
        # Create a pure black version on white background
        black_img = Image.new("RGB", gray.size, "white")
        pixels = gray.load()
        black_pixels = black_img.load()
        for y in range(gray.size[1]):
            for x in range(gray.size[0]):
                if pixels[x, y] < 250:  # Not white
                    black_pixels[x, y] = (0, 0, 0)  # Pure black
        
        # Resize maintaining aspect ratio with higher quality
        aspect_ratio = black_img.width / black_img.height
        new_height = target_height
        new_width = int(target_height * aspect_ratio)
        black_img = black_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return black_img
    except Exception as e:
        print(f"Warning: Could not load logo {logo_path}: {e}")
        return None


def create_pdf_report(data_file: Path, output_pdf: Path):
    """Create comprehensive A4 PDF report with 80s scientific aesthetic"""
    
    print(f"\nGenerating A4 PDF Report: {output_pdf}")
    print("=" * 60)
    
    # Read and parse data file
    lines = read_file_lines(str(data_file))
    metadata = parse_metadata(lines)
    
    # If sample name is Unknown, extract from filename
    if metadata['sample_name'] == 'Unknown':
        metadata['sample_name'] = data_file.stem  # Get filename without extension
    
    pixels, adcs = parse_lines_to_arrays(lines)
    
    # Estimate dark and calculate intensity
    adc_dark, _ = estimate_dark(pixels, adcs)
    intensities = adc_dark - adcs
    
    # Load calibration
    calib_points = load_calibration_points()
    wavelengths = apply_calibration(pixels, metadata['calibration_coeffs'])
    
    # Load logos
    script_dir = Path(__file__).parent.parent
    astrolens_logo = load_and_convert_logo(script_dir / "assets" / "astrolens.png", target_height=80)
    pyspec_logo = load_and_convert_logo(script_dir / "assets" / "icon.png", target_height=80, convert_yellow_to_white=True)
    
    # Create PDF with matplotlib
    with PdfPages(output_pdf) as pdf:
        # A4 size in inches (210mm x 297mm)
        fig = plt.figure(figsize=(8.27, 11.69), facecolor='white')
        
        # Use monospace font for 80s look
        plt.rcParams['font.family'] = 'monospace'
        plt.rcParams['font.size'] = 9
        
        # ============= HEADER SECTION =============
        # Add logos at top
        logo_y = 0.96
        if astrolens_logo:
            ax_logo1 = fig.add_axes([0.05, logo_y, 0.15, 0.04])
            ax_logo1.imshow(astrolens_logo)
            ax_logo1.axis('off')
        
        if pyspec_logo:
            ax_logo2 = fig.add_axes([0.80, logo_y, 0.15, 0.04])
            ax_logo2.imshow(pyspec_logo)
            ax_logo2.axis('off')
        
        # Title (removed to avoid overlap)
        # fig.text(0.5, 0.93, 'SPECTROSCOPY DATA ANALYSIS REPORT', 
        #         ha='center', va='top', fontsize=14, weight='bold', family='monospace')
        # fig.text(0.5, 0.91, '═' * 70, 
        #         ha='center', va='top', fontsize=8, family='monospace')
        
        # ============= METADATA SECTION =============
        meta_y_start = 0.95
        
        # Format integration time with appropriate unit
        formatted_int_time = format_time_with_unit(metadata['integration_time'])
        
        meta_text = f"""
-----------------------------------------------------------------------------------------------------------------------------------------
  ACQUISITION PARAMETERS                                                                                                        
-----------------------------------------------------------------------------------------------------------------------------------------
  Name:                      {metadata['sample_name']:<45s}
  Date:                      {metadata['date']:<25s}   Time:                      {metadata['time']:<25s}

  TIMING CONFIGURATION                                                                                                          
  SH Period:                 {metadata['sh_period']:<25s}   ICG Period:                {metadata['icg_period']:<25s}
  Integration Time:          {formatted_int_time:<25s}

  DATA STATISTICS                                                                                                               
  Average Count:             {metadata['average_count']:<25s}   Total Pixels:              {len(pixels):<25d}
-----------------------------------------------------------------------------------------------------------------------------------------
"""
        fig.text(0.05, meta_y_start, meta_text, 
                va='top', fontsize=6.5, family='monospace', linespacing=1.3)
        
        # ============= RAW MODE GRAPH =============
        ax1 = fig.add_axes([0.10, 0.62, 0.85, 0.16])
        ax1.plot(pixels, adcs, 'k-', linewidth=0.5)
        ax1.axhline(adc_dark, color='k', linestyle=':', linewidth=0.8, alpha=0.7)
        ax1.set_xlabel('PIXEL NUMBER', fontsize=8, weight='bold', family='monospace')
        ax1.set_ylabel('ADC COUNTS', fontsize=8, weight='bold', family='monospace')
        ax1.set_title('RAW MODE: PIXEL vs ADC COUNTS', 
                     fontsize=9, weight='bold', family='monospace', pad=10)
        ax1.grid(True, linestyle=':', linewidth=0.3, color='gray', alpha=0.5)
        ax1.spines['top'].set_linewidth(0.5)
        ax1.spines['right'].set_linewidth(0.5)
        ax1.spines['bottom'].set_linewidth(0.5)
        ax1.spines['left'].set_linewidth(0.5)
        # Invert y-axis to flip graph vertically
        ax1.invert_yaxis()
        
        # Shade dummy pixel regions (no label)
        ax1.axvspan(1, 32, alpha=0.1, color='gray')
        ax1.axvspan(3679, 3694, alpha=0.1, color='gray')
        
        # ============= SPECTROSCOPY MODE GRAPH =============
        ax2 = fig.add_axes([0.10, 0.36, 0.85, 0.16])
        ax2.plot(wavelengths, intensities, 'k-', linewidth=0.5)
        ax2.set_xlabel('WAVELENGTH (nm)', fontsize=8, weight='bold', family='monospace')
        ax2.set_ylabel('INTENSITY (a.u.)', fontsize=8, weight='bold', family='monospace')
        ax2.set_title('SPECTROSCOPY MODE: WAVELENGTH vs INTENSITY', 
                     fontsize=9, weight='bold', family='monospace', pad=10)
        ax2.grid(True, linestyle=':', linewidth=0.3, color='gray', alpha=0.5)
        ax2.spines['top'].set_linewidth(0.5)
        ax2.spines['right'].set_linewidth(0.5)
        ax2.spines['bottom'].set_linewidth(0.5)
        ax2.spines['left'].set_linewidth(0.5)
        
        # ============= CALIBRATION SECTION =============
        # Split into two columns: table on left, graph on right
        
        # Calibration points table (positioned more to the right)
        cal_y_start = 0.28
        cal_table = f"""
------------------------------------------------
  CALIBRATION POINTS (4-PT POLYNOMIAL)        
------------------------------------------------
  Point          Pixel          Wavelength (nm)          
------------------------------------------------
"""
        for i, point in enumerate(calib_points, 1):
            cal_table += f"    {i}            {point['pixel']:>5d}                {point['wavelength']:>7.2f}              \n"
        
        cal_table += """------------------------------------------------
"""
        fig.text(0.05, cal_y_start, cal_table, 
                va='top', fontsize=6.5, family='monospace', linespacing=1.3)
        
        # ============= CALIBRATION CURVE GRAPH (right side) =============
        ax3 = fig.add_axes([0.48, 0.08, 0.47, 0.20])
        
        # Plot calibration curve
        pixel_vals = [p["pixel"] for p in calib_points]
        wavelength_vals = [p["wavelength"] for p in calib_points]
        coeffs = np.polyfit(pixel_vals, wavelength_vals, 3)
        polynomial = np.poly1d(coeffs)
        
        x_curve = np.linspace(0, 3693, 200)
        y_curve = polynomial(x_curve)
        
        ax3.plot(x_curve, y_curve, 'k-', linewidth=1.2, label='Calibration Curve')
        ax3.plot(pixel_vals, wavelength_vals, 'ko', markersize=6, 
                markerfacecolor='white', markeredgewidth=1.5, label='Calib Points')
        
        ax3.set_xlabel('PIXEL NUMBER', fontsize=8, weight='bold', family='monospace')
        ax3.set_ylabel('WAVELENGTH (nm)', fontsize=8, weight='bold', family='monospace')
        ax3.set_title('CALIBRATION CURVE', 
                     fontsize=9, weight='bold', family='monospace', pad=10)
        ax3.grid(True, linestyle=':', linewidth=0.3, color='gray', alpha=0.5)
        ax3.legend(loc='best', fontsize=6, frameon=True)
        ax3.spines['top'].set_linewidth(0.5)
        ax3.spines['right'].set_linewidth(0.5)
        ax3.spines['bottom'].set_linewidth(0.5)
        ax3.spines['left'].set_linewidth(0.5)
        
        # Footer
        footer_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | pySPEC Spectroscopy System | www.AstroLens.net"
        fig.text(0.5, 0.01, footer_text, 
                ha='center', va='bottom', fontsize=6, family='monospace', style='italic')
        
        # Save page to PDF
        pdf.savefig(fig, facecolor='white', edgecolor='none')
        plt.close(fig)
    
    print(f"\n✓ PDF Report generated successfully: {output_pdf}")
    print("=" * 60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate A4 PDF scientific report from TCD1304 spectroscopy data (.dat files)"
    )
    parser.add_argument(
        "infile",
        nargs="?",
        default=None,
        help="Path to .dat file (if omitted, a file dialog will open)"
    )
    args = parser.parse_args()
    
    # Select input file
    infile_path: Path | None = None
    if args.infile:
        infile_path = Path(args.infile).expanduser().resolve()
        if not infile_path.is_file():
            print(f"Error: File not found: {infile_path}", file=sys.stderr)
            sys.exit(2)
    else:
        chosen = choose_file_with_dialog()
        if chosen is None:
            p = input("No file chosen. Enter path to .dat file (or press Enter to quit): ").strip()
            if not p:
                print("No file provided. Exiting.")
                sys.exit(1)
            infile_path = Path(p).expanduser().resolve()
        else:
            infile_path = chosen
    
    if not infile_path or not infile_path.is_file():
        print(f"Input file not found: {infile_path}", file=sys.stderr)
        sys.exit(2)
    
    # Generate output PDF name
    output_pdf = infile_path.parent / f"{infile_path.stem}_report.pdf"
    
    try:
        create_pdf_report(infile_path, output_pdf)
        print(f"\n✓ Success! Open the report: {output_pdf}")
    except Exception as e:
        print(f"\n✗ Error generating report: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
