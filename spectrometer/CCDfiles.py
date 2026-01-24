# Copyright (c) 2019 Esben Rossel
# All rights reserved.
#
# Author: Esben Rossel <esbenrossel@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.


import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from PIL import Image, ImageTk
from io import BytesIO
import csv
import numpy as np
from datetime import datetime
from spectrometer.calibration import default_calibration

from spectrometer import CCDpanelsetup, CCDplots, configuration
from utils import plotgraph


def openfile(self, CCDplot: CCDplots.BuildPlot):
    filename = filedialog.askopenfilename(
        defaultextension=".dat", title="Open file", parent=self
    )
    if not filename:
        return

    try:
        # Use the robust readers from utils.plotgraph to parse the file
        lines = plotgraph.read_file_lines(filename)
        pixels, adcs = plotgraph.parse_lines_to_arrays(lines)

        # Update config.rxData16 from the parsed ADCs (map by pixel index if possible)
        try:
            for p, a in zip(pixels, adcs):
                idx = int(p) - 1
                if 0 <= idx < CCDplot.config.rxData16.size:
                    CCDplot.config.rxData16[idx] = int(round(a))
        except Exception:
            n = min(len(adcs), CCDplot.config.rxData16.size)
            CCDplot.config.rxData16[:n] = np.round(adcs[:n]).astype(
                CCDplot.config.rxData16.dtype
            )
        # Try to extract SH/ICG info from first few header lines
        try:
            for ln in lines[:6]:
                if "SH-period" in ln or "SH-period:" in ln:
                    nums = [
                        int("".join(ch for ch in tok if ch.isdigit()))
                        for tok in ln.split()
                        if any(c.isdigit() for c in tok)
                    ]
                    if len(nums) >= 2:
                        CCDplot.config.sh_sent = np.uint32(nums[0])
                        CCDplot.config.icg_sent = np.uint32(nums[1])
                        break
        except Exception:
            pass

        # No standalone preview window: we only update the main plot with the loaded data

        # Update the main plot with the loaded data
        CCDpanelsetup.BuildPanel.updateplot(self, CCDplot)

        # Enable save button now that data has been loaded
        try:
            self.bsave.config(state=tk.NORMAL)
        except Exception as e:
            print(f"Warning: Could not enable save button: {e}")

        # Enable save regression button now that data has been loaded
        try:
            if hasattr(self, "bsave_regression") and hasattr(
                self, "_set_reg_save_enabled"
            ):
                self._set_reg_save_enabled(True)
        except Exception as e:
            print(f"Warning: Could not enable save regression button: {e}")

        # Enable subtract button now that data has been loaded
        try:
            if hasattr(self, "bsubtract"):
                self.bsubtract.config(state=tk.NORMAL)
        except Exception as e:
            print(f"Warning: Could not enable subtract button: {e}")

    except IOError:
        messagebox.showerror("pySPEC", "There's a problem opening the file.")


def savefile(self, config: configuration.Config):
    filename = filedialog.asksaveasfilename(
        defaultextension=".dat", title="Save file as", parent=self
    )
    if not filename:  # User cancelled
        return

    try:
        with open(filename, mode="w") as csvfile:
            writeCSV = csv.writer(csvfile, delimiter=" ")

            # Header
            writeCSV.writerow(["#Data", "from", "the", "TCD1304", "linear", "CCD"])

            # Date and Time - always save current datetime
            current_datetime = datetime.now()
            writeCSV.writerow(
                [
                    "#Date:",
                    current_datetime.strftime("%Y-%m-%d"),
                    "Time:",
                    current_datetime.strftime("%H:%M:%S"),
                ]
            )

            # Extract just the filename without path
            sample_name = filename.split("/")[-1].split("\\")[-1].replace(".dat", "")
            writeCSV.writerow(["#Sample-name:", sample_name])

            # Column description
            writeCSV.writerow(
                [
                    "#column",
                    "1",
                    "=",
                    "pixelnumber",
                    ",",
                    "column",
                    "2",
                    "=",
                    "pixelvalue",
                ]
            )
            writeCSV.writerow(
                ["#Pixel", "1-32", "and", "3679-3694", "are", "dummy", "pixels"]
            )

            # Timing configuration
            sh_period = str(config.sh_sent) if hasattr(config, "SHsent") else "200"
            icg_period = (
                str(config.icg_sent) if hasattr(config, "ICGsent") else "100000"
            )
            int_time = (
                str(float(config.sh_sent) / 2) if hasattr(config, "SHsent") else "100.0"
            )

            writeCSV.writerow(
                [
                    "#SH-period:",
                    sh_period,
                    "",
                    "ICG-period:",
                    icg_period,
                    "",
                    "Integration",
                    "time:",
                    int_time,
                    "µs",
                ]
            )

            # Add firmware settings (always save actual values, never N/A)
            avg_value = (
                config.avg_n[0]
                if hasattr(config, "AVGn") and len(config.avg_n) > 0
                else 0
            )
            mclk_value = config.mclk if hasattr(config, "MCLK") else 2000000
            writeCSV.writerow(
                [
                    "#Firmware-settings:",
                    "AVG:",
                    str(avg_value),
                    "MCLK:",
                    str(mclk_value),
                    "Hz",
                ]
            )

            # Add average count (calculate from valid pixels, not dummy pixels)
            try:
                if hasattr(config, "rxData16") and len(config.rxData16) > 3679:
                    avg_count = float(np.mean(config.rxData16[32:3679]))
                    writeCSV.writerow(["#Average-count:", f"{avg_count:.2f}"])
                else:
                    writeCSV.writerow(["#Average-count:", "0.00"])
            except Exception as e:
                print(f"Warning: Could not calculate average count: {e}")
                writeCSV.writerow(["#Average-count:", "0.00"])

            # Add spectroscopy mode
            spec_mode = (
                config.spectroscopy_mode
                if hasattr(config, "spectroscopy_mode")
                else False
            )
            writeCSV.writerow(["#Spectroscopy-mode:", str(spec_mode)])

            # Add calibration coefficients - calculate from calibration points
            try:
                if hasattr(default_calibration, "calibration_data"):
                    points = default_calibration.calibration_data.get("points", [])
                    if len(points) == 4:
                        pixel_vals = [p["pixel"] for p in points]
                        wavelength_vals = [p["wavelength"] for p in points]
                        coeffs = np.polyfit(pixel_vals, wavelength_vals, 3)
                        coeff_str = ",".join([f"{c:.10e}" for c in coeffs])
                        writeCSV.writerow(["#Calibration-coefficients:", coeff_str])
                    else:
                        # Default linear calibration
                        writeCSV.writerow(["#Calibration-coefficients:", "0,1,0,0"])
                else:
                    writeCSV.writerow(["#Calibration-coefficients:", "0,1,0,0"])
            except Exception as e:
                print(f"Warning: Could not save calibration coefficients: {e}")
                writeCSV.writerow(["#Calibration-coefficients:", "0,1,0,0"])

            # Write pixel data
            for i in range(3694):
                writeCSV.writerow([str(i + 1), str(config.rxData16[i])])

            print(f"Successfully saved spectrum data to: {filename}")

    except IOError as e:
        print(f"IOError saving file: {e}")
        messagebox.showerror("pySPEC", "There's a problem saving the file.")
    except Exception as e:
        print(f"Error saving file: {e}")
        messagebox.showerror("pySPEC", f"Error saving file: {str(e)}")


def savefile_with_regression(self, config: configuration.Config):
    """Save file with regression parameters included in the header"""
    filename = filedialog.asksaveasfilename(
        defaultextension=".dat", title="Save file with regression as", parent=self
    )
    if not filename:  # User cancelled
        return

    try:
        from datetime import datetime
        from spectrometer.calibration import default_calibration

        with open(filename, mode="w") as csvfile:
            writeCSV = csv.writer(csvfile, delimiter=" ")

            # Header
            writeCSV.writerow(["#Data", "from", "the", "TCD1304", "linear", "CCD"])

            # Date and Time - always save current datetime
            current_datetime = datetime.now()
            writeCSV.writerow(
                [
                    "#Date:",
                    current_datetime.strftime("%Y-%m-%d"),
                    "Time:",
                    current_datetime.strftime("%H:%M:%S"),
                ]
            )

            # Extract just the filename without path
            sample_name = filename.split("/")[-1].split("\\")[-1].replace(".dat", "")
            writeCSV.writerow(["#Sample-name:", sample_name])

            # Column description
            writeCSV.writerow(
                [
                    "#column",
                    "1",
                    "=",
                    "pixelnumber",
                    ",",
                    "column",
                    "2",
                    "=",
                    "pixelvalue",
                ]
            )
            writeCSV.writerow(
                ["#Pixel", "1-32", "and", "3679-3694", "are", "dummy", "pixels"]
            )

            # Timing configuration
            sh_period = str(config.sh_sent) if hasattr(config, "SHsent") else "200"
            icg_period = (
                str(config.icg_sent) if hasattr(config, "ICGsent") else "100000"
            )
            int_time = (
                str(float(config.sh_sent) / 2) if hasattr(config, "SHsent") else "100.0"
            )

            writeCSV.writerow(
                [
                    "#SH-period:",
                    sh_period,
                    "",
                    "ICG-period:",
                    icg_period,
                    "",
                    "Integration",
                    "time:",
                    int_time,
                    "µs",
                ]
            )

            # Add firmware settings (always save actual values, never N/A)
            avg_value = (
                config.avg_n[0]
                if hasattr(config, "AVGn") and len(config.avg_n) > 0
                else 0
            )
            mclk_value = config.mclk if hasattr(config, "MCLK") else 2000000
            writeCSV.writerow(
                [
                    "#Firmware-settings:",
                    "AVG:",
                    str(avg_value),
                    "MCLK:",
                    str(mclk_value),
                    "Hz",
                ]
            )

            # Add average count (calculate from valid pixels, not dummy pixels)
            try:
                if hasattr(config, "rxData16") and len(config.rxData16) > 3679:
                    avg_count = float(np.mean(config.rxData16[32:3679]))
                    writeCSV.writerow(["#Average-count:", f"{avg_count:.2f}"])
                else:
                    writeCSV.writerow(["#Average-count:", "0.00"])
            except Exception as e:
                print(f"Warning: Could not calculate average count: {e}")
                writeCSV.writerow(["#Average-count:", "0.00"])

            # Add spectroscopy mode
            spec_mode = (
                config.spectroscopy_mode
                if hasattr(config, "spectroscopy_mode")
                else False
            )
            writeCSV.writerow(["#Spectroscopy-mode:", str(spec_mode)])

            # Add calibration coefficients - calculate from calibration points
            try:
                if hasattr(default_calibration, "calibration_data"):
                    points = default_calibration.calibration_data.get("points", [])
                    if len(points) == 4:
                        pixel_vals = [p["pixel"] for p in points]
                        wavelength_vals = [p["wavelength"] for p in points]
                        coeffs = np.polyfit(pixel_vals, wavelength_vals, 3)
                        coeff_str = ",".join([f"{c:.10e}" for c in coeffs])
                        writeCSV.writerow(["#Calibration-coefficients:", coeff_str])
                    else:
                        # Default linear calibration
                        writeCSV.writerow(["#Calibration-coefficients:", "0,1,0,0"])
                else:
                    writeCSV.writerow(["#Calibration-coefficients:", "0,1,0,0"])
            except Exception as e:
                print(f"Warning: Could not save calibration coefficients: {e}")
                writeCSV.writerow(["#Calibration-coefficients:", "0,1,0,0"])

            # Add regression parameters if enabled
            try:
                if hasattr(self, "ph_checkbox_var") and self.ph_checkbox_var.get() == 1:
                    # Get smoothing value from slider
                    try:
                        sval = float(self.ph_scale.get())
                    except Exception:
                        sval = 100.0
                    # Convert slider value to smoothing factor (10->0, 1000->49.5)
                    smooth = max(0.0, (sval - 10.0) / 20.0)

                    writeCSV.writerow(["#Regression-enabled:", "True"])
                    writeCSV.writerow(["#Regression-method:", "spline"])
                    writeCSV.writerow(["#Regression-smooth:", f"{smooth:.6f}"])
                else:
                    writeCSV.writerow(["#Regression-enabled:", "False"])
            except Exception as e:
                print(f"Warning: Could not save regression parameters: {e}")
                writeCSV.writerow(["#Regression-enabled:", "False"])

            # Write pixel data
            for i in range(3694):
                writeCSV.writerow([str(i + 1), str(config.rxData16[i])])

            print(f"Successfully saved spectrum data with regression to: {filename}")

    except IOError as e:
        print(f"IOError saving file: {e}")
        messagebox.showerror("pySPEC", "There's a problem saving the file.")
    except Exception as e:
        print(f"Error saving file: {e}")
        messagebox.showerror("pySPEC", f"Error saving file: {str(e)}")
