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

from spectrometer import config, CCDpanelsetup
from utils import plotgraph


def openfile(self, CCDplot):
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
                if 0 <= idx < config.rxData16.size:
                    config.rxData16[idx] = int(round(a))
        except Exception:
            n = min(len(adcs), config.rxData16.size)
            config.rxData16[:n] = np.round(adcs[:n]).astype(config.rxData16.dtype)

        # Try to extract SH/ICG info from first few header lines
        try:
            for ln in lines[:6]:
                if "SH-period" in ln or "SH-period:" in ln:
                    nums = [int(''.join(ch for ch in tok if ch.isdigit())) for tok in ln.split() if any(c.isdigit() for c in tok)]
                    if len(nums) >= 2:
                        config.SHsent = nums[0]
                        config.ICGsent = nums[1]
                        break
        except Exception:
            pass

        # No standalone preview window: we only update the main plot with the loaded data

        # Update the main plot with the loaded data
        CCDpanelsetup.BuildPanel.updateplot(self, CCDplot)

        # Enable save button now that data has been loaded
        try:
            self.bsave.config(state=tk.NORMAL)
        except Exception:
            pass

    except IOError:
        messagebox.showerror(
            "pySPEC", "There's a problem opening the file."
        )


def savefile(self):
    filename = filedialog.asksaveasfilename(
        defaultextension=".dat", title="Save file as", parent=self
    )
    try:
        with open(filename, mode="w") as csvfile:
            writeCSV = csv.writer(csvfile, delimiter=" ")
            writeCSV.writerow(["#Data", "from", "the", "TCD1304", "linear", "CCD"])
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
                ["#Pixel", "1-32", "and", "3679-3694", "and", "are", "dummy", "pixels"]
            )
            writeCSV.writerow(
                [
                    "#SH-period:",
                    str(config.SHsent),
                    "",
                    "",
                    "",
                    "ICG-period:",
                    str(config.ICGsent),
                    "",
                    "",
                    "",
                    "Integration",
                    "time:",
                    str(config.SHsent / 2),
                    "µs",
                ]
            )
            for i in range(3694):
                writeCSV.writerow([str(i + 1), str(config.rxData16[i])])

    except IOError:
        messagebox.showerror(
            "pySPEC", "There's a problem saving the file."
        )
