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

import os
import tkinter as tk
from tkinter import ttk, colorchooser
import numpy as np
import serial
import math
import webbrowser
from PIL import Image, ImageTk

from spectrometer import config, CCDserial, CCDfiles, widgets
from spectrometer.calibration import default_calibration
from utils import plotgraph


class BuildPanel(ttk.Frame):
    def __init__(self, master, CCDplot, SerQueue):
        # geometry-rows for packing the grid
        progress_var = tk.IntVar()

        super().__init__(master)

        # Store CCDplot reference for callbacks
        self.CCDplot = CCDplot

        # Initialize plot colors
        self.main_plot_color = "#1f77b4"  # Default matplotlib blue
        self.regression_color = "#d62728"  # Default red
        self.compare_color = "#2ca02c"  # Default green for comparison data

        # Initialize comparison data storage
        self.comparison_data = None
        self.comparison_filename = None

        # Create all widgets and space between them
        self.header_fields()
        self.mode_fields()
        self.devicefields()
        self.CCDparamfields()
        self.collectmodefields()
        self.collectfields(SerQueue, progress_var)
        self.plotmodefields(CCDplot)
        self.saveopenfields(CCDplot)
        self.updateplotfields(CCDplot)
        self.aboutbutton()

    def header_fields(self):
        """Add header and close button"""
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill=tk.X, pady=10)

        self.bclose = ttk.Button(
            self.header_frame,
            text="X",
            style="Accent.TButton",
            command=lambda root=self.master: root.destroy(),
        )
        self.bclose.pack(side=tk.RIGHT, padx=5, pady=10)

        self.lheader = ttk.Label(
            self.header_frame,
            text="pySPEC",
            font=("Avenir", 16, "bold"),
            foreground="#ffc200",
        )
        self.lheader.pack(side=tk.RIGHT, pady=10, padx=5)

    def mode_fields(self):
        """Add spectroscopy mode toggle"""
        self.operation_mode_frame = ttk.Frame(self)
        self.operation_mode_frame.pack(fill=tk.X, padx=5, pady=5)

        self.mode_var = tk.IntVar(value=0)  # 0 = Regular, 1 = Spectroscopy

        self.r_regular = ttk.Radiobutton(
            self.operation_mode_frame,
            text="Regular Mode",
            variable=self.mode_var,
            value=0,
            command=self.mode_changed,
        )
        self.r_regular.pack(side=tk.LEFT, padx=5)

        self.r_spectroscopy = ttk.Radiobutton(
            self.operation_mode_frame,
            text="Spectroscopy Mode",
            variable=self.mode_var,
            value=1,
            command=self.mode_changed,
        )
        self.r_spectroscopy.pack(side=tk.LEFT, padx=5)

    def mode_changed(self):
        """Handle mode switching"""
        config.spectroscopy_mode = bool(self.mode_var.get())

        if config.spectroscopy_mode:
            # Auto-open calibration window in spectroscopy mode
            default_calibration.open_calibration_window(
                self.master, on_apply_callback=self.CCDplot.replot_current_spectrum
            )

        # Update the plot immediately with the correct axis
        self.update_plot_axis()

        # Update spectrum colors when mode changes
        self.CCDplot.set_show_colors(self.show_colors.get())
        self.CCDplot.canvas.draw()

    def update_plot_axis(self):
        """Update the plot axis based on current mode"""
        if hasattr(self.CCDplot, "a") and self.CCDplot.a is not None:
            if config.spectroscopy_mode:
                # Use wavelength calibration for spectroscopy mode
                if hasattr(default_calibration, "apply") and callable(
                    default_calibration.apply
                ):
                    x_values = default_calibration.apply(np.arange(3694))
                    x_label = "Wavelength (nm)"
                    # Normal direction: lower wavelengths on left, higher on right
                    self.CCDplot.a.set_xlim(
                        x_values[0], x_values[-1]
                    )  # Normal direction
                else:
                    # Fallback to pixels if no calibration
                    x_values = np.arange(3694)
                    x_label = "Pixelnumber (No Calibration)"
                    self.CCDplot.a.set_xlim(x_values[0], x_values[-1])  # Normal
            else:
                # Use pixel numbers for regular mode
                x_values = np.arange(3694)
                x_label = "Pixelnumber"
                self.CCDplot.a.set_xlim(x_values[0], x_values[-1])  # Normal

            # Update the axis label
            self.CCDplot.a.set_xlabel(x_label)

            # Redraw the canvas
            if hasattr(self.CCDplot, "canvas"):
                self.CCDplot.canvas.draw()

    def devicefields(self):
        # device setup - variables, widgets and traces associated with the device entrybox
        device_frame = widgets.CollapsibleTTK(self, title="Device Setup")
        device_frame.pack(fill=tk.X, pady=5)

        # variables
        self.device_address = tk.StringVar()
        self.device_status = tk.StringVar()
        self.device_statuscolor = tk.StringVar()

        # RX port
        rx_row = ttk.Frame(device_frame.sub_frame)
        rx_row.pack(fill=tk.X, pady=5)

        self.ldevice = ttk.Label(rx_row, text="COM port (RX/TX):", justify="right")
        self.ldevice.pack(side=tk.LEFT, padx=5)

        self.edevice = ttk.Entry(
            rx_row, textvariable=self.device_address, justify="left"
        )
        self.edevice.pack(side=tk.RIGHT, padx=5)

        # RX status
        self.ldevicestatus = tk.Label(
            device_frame.sub_frame, textvariable=self.device_status, fg="#ffffff"
        )
        self.ldevicestatus.pack(anchor=tk.E, padx=5)

        # setup trace to check if the device exists
        self.device_address.trace_add(
            "write",
            lambda name, index, mode, Device=self.device_address, status=self.device_status, colr=self.ldevicestatus: self.DEVcallback(
                name, index, mode, Device, status, colr
            ),
        )
        self.device_address.set(config.port)

        # TX port field (optional - if empty, uses same as RX)
        self.device_address_tx = tk.StringVar()
        self.device_status_tx = tk.StringVar(value="Using RX port")

        tx_row = ttk.Frame(device_frame.sub_frame)
        tx_row.pack(fill=tk.X, pady=5)

        self.ldevice_tx = ttk.Label(tx_row, text="COM port (TX):", justify="right")
        self.ldevice_tx.pack(side=tk.LEFT, padx=5)

        self.edevice_tx = ttk.Entry(
            tx_row, textvariable=self.device_address_tx, justify="left"
        )
        self.edevice_tx.pack(side=tk.RIGHT, padx=5)

        # TX status
        self.ldevicestatus_tx = tk.Label(
            device_frame.sub_frame, textvariable=self.device_status_tx, fg="#888888"
        )
        self.ldevicestatus_tx.pack(anchor=tk.E, padx=5)

        # setup trace to check if the TX device exists
        self.device_address_tx.trace_add(
            "write",
            lambda name, index, mode, Device=self.device_address_tx, status=self.device_status_tx, colr=self.ldevicestatus_tx: self.DEVcallback_tx(
                name, index, mode, Device, status, colr
            ),
        )
        if config.port_tx:
            self.device_address_tx.set(config.port_tx)

        # Update status
        self.DEVcallback(
            None,
            None,
            None,
            self.device_address,
            self.device_status,
            self.ldevicestatus,
        )

        # Update TX status
        self.DEVcallback_tx(
            None,
            None,
            None,
            self.device_address_tx,
            self.device_status_tx,
            self.ldevicestatus_tx,
        )

        # firmware selection
        firmware_row = ttk.Frame(device_frame.sub_frame)
        firmware_row.pack(fill=tk.X, pady=5)

        self.lfirmware = ttk.Label(firmware_row, text="Firmware:", justify="right")
        self.lfirmware.pack(side=tk.LEFT, padx=5)

        self.firmware_type = tk.StringVar(value="STM32F40x")
        self.firmware_dropdown = ttk.Combobox(
            firmware_row,
            textvariable=self.firmware_type,
            values=["STM32F40x", "STM32F103"],
            state="readonly",
        )
        self.firmware_dropdown.pack(side=tk.RIGHT, padx=5)
        self.firmware_type.trace_add("write", self.update_firmware)

    def update_firmware(self, *args):
        if self.firmware_type.get() == "STM32F103":
            config.MCLK = 800000
            config.min_sh = 8
            config.max_sh = 65535
        else:
            config.MCLK = 2000000
            config.min_sh = 20
            config.max_sh = 4294967295
        # Update timings
        self.calculate_timings()

    def CCDparamfields(self):
        # CCD parameters - variables, widgets and traces associated with setting exposure
        ccd_frame = widgets.CollapsibleTTK(self, title="CCD Parameters")
        ccd_frame.pack(fill=tk.X, pady=5)

        # variables
        self.SH = tk.StringVar()
        self.ICG = tk.StringVar()
        self.tint_status = tk.StringVar()
        self.tint_statuscolor = tk.StringVar()
        self.tint_value = tk.StringVar()  # For exposure time numeric input
        self.tint_unit = tk.StringVar(value="ms")  # Default unit

        # Exposure time input
        exposure_row = ttk.Frame(ccd_frame.sub_frame)
        exposure_row.pack(fill=tk.X, pady=5)

        self.l_exposure = ttk.Label(exposure_row, text="Exposure Time:")
        self.l_exposure.pack(side=tk.LEFT, padx=5)

        self.unit_dropdown = ttk.Combobox(
            exposure_row,
            textvariable=self.tint_unit,
            values=["us", "ms", "s", "min"],
            state="readonly",
            width=5,
        )
        self.unit_dropdown.pack(side=tk.RIGHT, padx=5)

        self.e_tint = ttk.Entry(
            exposure_row, textvariable=self.tint_value, justify="left", width=10
        )
        self.e_tint.pack(side=tk.RIGHT, padx=5)

        # Original SH/ICG fields
        sh_row = ttk.Frame(ccd_frame.sub_frame)
        sh_row.pack(fill=tk.X, pady=5)

        self.lSH = ttk.Label(sh_row, text="SH-period:")
        self.lSH.pack(side=tk.LEFT, padx=5)

        self.eSH = ttk.Entry(sh_row, textvariable=self.SH, justify="left")
        self.eSH.pack(side=tk.RIGHT, padx=5)

        icg_row = ttk.Frame(ccd_frame.sub_frame)
        icg_row.pack(fill=tk.X, pady=5)

        self.lICG = ttk.Label(icg_row, text="ICG-period:")
        self.lICG.pack(side=tk.LEFT, padx=5)

        self.eICG = ttk.Entry(icg_row, textvariable=self.ICG, justify="left")
        self.eICG.pack(side=tk.RIGHT, padx=5)

        # Status labels
        self.lccdstatus = tk.Label(ccd_frame.sub_frame, textvariable=self.tint_status)
        self.lccdstatus.pack(anchor=tk.E, padx=5, pady=5)

        self.ltint = tk.Label(ccd_frame.sub_frame, textvariable=self.tint_statuscolor)
        self.ltint.pack(anchor=tk.E, padx=5, pady=5)

        # Set initial values
        self.SH.set(str(config.SHperiod))
        self.ICG.set(str(config.ICGperiod))

        # Traces for auto-calculation
        self.tint_value.trace_add("write", self.calculate_timings)
        self.tint_unit.trace_add("write", self.calculate_timings)
        self.SH.trace_add(
            "write",
            lambda name, index, mode: self.ICGSHcallback(
                name,
                index,
                mode,
                self.tint_status,
                self.tint_statuscolor,
                self.lccdstatus,
                self.SH,
                self.ICG,
            ),
        )
        self.ICG.trace_add(
            "write",
            lambda name, index, mode: self.ICGSHcallback(
                name,
                index,
                mode,
                self.tint_status,
                self.tint_statuscolor,
                self.lccdstatus,
                self.SH,
                self.ICG,
            ),
        )

        # Set initial exposure time input based on config
        tint_sec = float(config.SHperiod) / config.MCLK
        if tint_sec < 1e-3:
            self.tint_value.set(str(round(tint_sec * 1e6, 2)))
            self.tint_unit.set("us")
        elif tint_sec < 1:
            self.tint_value.set(str(round(tint_sec * 1000, 2)))
            self.tint_unit.set("ms")
        elif tint_sec < 60:
            self.tint_value.set(str(round(tint_sec, 2)))
            self.tint_unit.set("s")
        else:
            self.tint_value.set(str(round(tint_sec / 60, 2)))
            self.tint_unit.set("min")

        # Initialize status by calling callback
        self.ICGSHcallback(
            None,
            None,
            None,
            self.tint_status,
            self.tint_statuscolor,
            self.lccdstatus,
            self.SH,
            self.ICG,
        )

    def calculate_timings(self, *args):
        try:
            tint_num = float(self.tint_value.get())
            unit = self.tint_unit.get()

            # Convert to seconds
            if unit == "s":
                tint_sec = tint_num
            elif unit == "ms":
                tint_sec = tint_num * 1e-3
            elif unit == "us":
                tint_sec = tint_num * 1e-6
            elif unit == "min":
                tint_sec = tint_num * 60
            else:
                raise ValueError("Invalid unit")

            # Calculate SH-period
            sh_period = int(round(tint_sec * config.MCLK))

            # Enforce limits
            sh_period = max(config.min_sh, min(sh_period, config.max_sh))

            # Automatically calculate n
            min_n = math.ceil(14776 / sh_period)
            n = max(1, min_n)

            # Calculate ICG-period
            icg_period = n * sh_period

            # Update config and fields
            config.SHperiod = np.uint32(sh_period)
            config.ICGperiod = np.uint32(icg_period)
            self.SH.set(str(sh_period))
            self.ICG.set(str(icg_period))

            # Trigger validation
            self.ICGSHcallback(
                None,
                None,
                None,
                self.tint_status,
                self.tint_statuscolor,
                self.lccdstatus,
                self.SH,
                self.ICG,
            )

        except ValueError:
            # Invalid input: set error status
            self.tint_status.set("Invalid exposure input!")
            self.lccdstatus.configure(fg="#ffc200")
            self.tint_statuscolor.set("invalid")

    def ICGSHcallback(self, name, index, mode, status, tint, colr, SH, ICG):
        try:
            config.SHperiod = np.uint32(int(SH.get()))
            config.ICGperiod = np.uint32(int(ICG.get()))
        except:
            print("SH or ICG not an integer")

        if config.SHperiod < 1:
            config.SHperiod = 1
        if config.ICGperiod < 1:
            config.ICGperiod = 1

        if (
            (config.ICGperiod % config.SHperiod)
            or (config.SHperiod < config.min_sh)
            or (config.ICGperiod < 14776)
        ):
            status.set("CCD pulse timing violation!")
            colr.configure(fg="#ffc200")
            print_tint = "invalid"
        else:
            status.set("CCD pulse timing correct.")
            colr.configure(fg="#ffffff")
            tint_sec = float(config.SHperiod) / config.MCLK
            if tint_sec < 1e-3:
                print_tint = str(round(tint_sec * 1e6, 2)) + " us"
            elif tint_sec < 1:
                print_tint = str(round(tint_sec * 1000, 2)) + " ms"
            elif tint_sec < 60:
                print_tint = str(round(tint_sec, 2)) + " s"
            else:
                print_tint = str(round(tint_sec / 60, 2)) + " min"

        tint.set("Integration time is " + print_tint)

    def modeset(self, CONTvar):
        config.AVGn[0] = CONTvar.get()

    def AVGcallback(self, AVGscale):
        config.AVGn[1] = np.uint8(self.AVGscale.get())
        self.AVGlabel.config(text=str(config.AVGn[1]))

    def RAWcallback(self, name, index, mode, invert, CCDplot):
        config.datainvert = invert.get()
        if config.datainvert == 0:
            self.cbalance.config(state=tk.DISABLED)
        else:
            self.cbalance.config(state=tk.NORMAL)
        self.updateplot(CCDplot)

    def MIRcallback(self, name, index, mode, mirror, CCDplot):
        """Callback when mirror checkbox changes"""
        config.datamirror = mirror.get()
        self.updateplot(CCDplot)

    def BALcallback(self, name, index, mode, balanced, CCDplot):
        config.balanced = balanced.get()
        self.updateplot(CCDplot)

    def DEVcallback(self, name, index, mode, Device, status, colr):
        config.port = Device.get()

        # Check if it's a simulation port
        if config.port in ["SIMULATION", "SIM", "TEST"]:
            status.set("Simulation mode active")
            colr.configure(fg="blue")
            # Set a special port name that our bridge will recognize
            config.port = "socket://localhost:9999"

        elif config.port.startswith(("socket://", "tcp://")):
            status.set("Socket connection")
            colr.configure(fg="blue")

        else:
            # Normal COM port checking
            try:
                ser = serial.Serial(config.port, config.baudrate, timeout=1)
                status.set("Port found")
                ser.close()
                colr.configure(fg="#ffffff")
            except serial.SerialException:
                status.set("Port not found")
                colr.configure(fg="#ffc200")

    def DEVcallback_tx(self, name, index, mode, Device, status, colr):
        tx_port = Device.get().strip()

        # If TX port is empty, use same as RX port
        if not tx_port:
            config.port_tx = None
            status.set("Using RX port")
            colr.configure(fg="#888888")
            return

        config.port_tx = tx_port

        # Check if it's a simulation port
        if config.port_tx in ["SIMULATION", "SIM", "TEST"]:
            status.set("Simulation mode active")
            colr.configure(fg="blue")
            # Set a special port name that our bridge will recognize
            config.port_tx = "socket://localhost:9999"

        elif config.port_tx.startswith(("socket://", "tcp://")):
            status.set("Socket connection")
            colr.configure(fg="blue")

        else:
            # Normal COM port checking
            try:
                ser = serial.Serial(config.port_tx, config.baudrate, timeout=1)
                status.set("Port found")
                ser.close()
                colr.configure(fg="#ffffff")
            except serial.SerialException:
                status.set("Port not found")
                colr.configure(fg="#ffc200")

    def updateplot(self, CCDplot):
        # This subtracts the ADC-pixel from ADC-dark
        if config.datainvert == 1:
            config.pltData16 = (
                config.rxData16[10] + config.rxData16[11]
            ) / 2 - config.rxData16
            # This subtracts the average difference between even and odd pixels from the even pixels
            if config.balanced == 1:
                config.offset = (
                    config.pltData16[18]
                    + config.pltData16[20]
                    + config.pltData16[22]
                    + config.pltData16[24]
                    - config.pltData16[19]
                    - config.pltData16[21]
                    - config.pltData16[23]
                    - config.pltData16[24]
                ) / 4
                for i in range(1847):
                    config.pltData16[2 * i] = config.pltData16[2 * i] - config.offset
        CCDplot.a.clear()

        # Capture current x-limits early so we can restore user zoom after redraw
        try:
            prev_xlim = (
                tuple(self.CCDplot.a.get_xlim())
                if hasattr(self.CCDplot, "a") and self.CCDplot.a is not None
                else None
            )
        except Exception:
            prev_xlim = None

        # Choose x-axis based on mode
        if config.spectroscopy_mode:
            # Use wavelength calibration for spectroscopy mode
            if hasattr(default_calibration, "apply") and callable(
                default_calibration.apply
            ):
                x_values = default_calibration.apply(np.arange(3694))
                x_label = "Wavelength (nm)"
            else:
                # Fallback to pixels if no calibration
                x_values = np.arange(3694)
                x_label = "Pixelnumber (No Calibration)"
        else:
            # Use pixel numbers for regular mode
            x_values = np.arange(3694)
            x_label = "Pixelnumber"

        # Axis limits will be restored later (preserve user zoom) — do not set them here

        # plot intensities
        if config.datainvert == 1:
            data = config.pltData16
            # main plot uses opacity from slider (default 1.0)
            try:
                alpha = float(self.opacity_scale.get()) / 100.0
            except Exception:
                alpha = 1.0
            # Apply optional left/right mirroring before plotting
            try:
                if getattr(config, "datamirror", 0) == 1:
                    data = data[::-1]
            except Exception:
                pass

            # Plot raw/intensity data directly
            CCDplot.a.plot(x_values, data, alpha=alpha, color=self.main_plot_color)
            CCDplot.a.set_ylabel("Intensity")
            CCDplot.a.set_xlabel(x_label)
            # Set Y-axis range for intensity plot
            CCDplot.a.set_ylim(-10, 2250)
        else:
            # plot raw data
            data = config.rxData16
            try:
                alpha = float(self.opacity_scale.get()) / 100.0
            except Exception:
                alpha = 1.0
            # Apply optional left/right mirroring before plotting
            try:
                if getattr(config, "datamirror", 0) == 1:
                    data = data[::-1]
            except Exception:
                pass

            # Plot raw data directly
            CCDplot.a.plot(x_values, data, alpha=alpha, color=self.main_plot_color)
            CCDplot.a.set_ylabel("ADCcount")
            CCDplot.a.set_xlabel(x_label)
            # Set Y-axis range for raw data plot
            CCDplot.a.set_ylim(-10, 4095)

        # Update spectrum background
        self.CCDplot.set_show_colors(self.show_colors.get())

        # If regression toggle is active, compute and plot interpolated curve
        try:
            if (
                getattr(self, "ph_checkbox_var", None)
                and self.ph_checkbox_var.get() == 1
            ):
                # Use the same data that was plotted (data variable)
                n = data.size
                pixels = np.arange(n)
                intensities = data.astype(float)

                # smoothing parameter from slider (map 0..100 -> 0.0..0.1)
                try:
                    sval = float(self.ph_scale.get())
                except Exception:
                    sval = 5.0
                # Use finer mapping so small slider changes at the low end have
                # a noticeable effect: divisor 1000 gives range 0.0..0.1
                smooth = max(0.0, float(sval) / 1000.0)

                interp_fn, interp_kind = plotgraph.make_interpolator(
                    pixels, intensities, method="spline", smooth=smooth
                )
                xs_pix = np.linspace(pixels.min(), pixels.max(), 2000)
                try:
                    ys_interp = interp_fn(xs_pix)
                    ys_interp = np.asarray(ys_interp, dtype=float)
                except Exception:
                    ys_interp = np.interp(xs_pix, pixels, intensities)

                # Map pixel x-coordinates to plot x-coordinates (pixels or calibrated wavelengths)
                if (
                    config.spectroscopy_mode
                    and hasattr(default_calibration, "apply")
                    and callable(default_calibration.apply)
                ):
                    xs_plot = default_calibration.apply(xs_pix.astype(int))
                else:
                    xs_plot = xs_pix

                # Plot interpolated curve as a distinct coloured line
                CCDplot.a.plot(
                    xs_plot,
                    ys_interp,
                    color=self.regression_color,
                    lw=0.9,
                    alpha=0.9,
                    label="interpolated",
                )
        except Exception:
            # don't let regression failures break the plotting
            pass

        # Plot comparison data if available
        if self.comparison_data is not None:
            try:
                # Assume comparison data is in the same format as main data
                # If it's a 2D array with x and y columns, use both
                if (
                    self.comparison_data.ndim == 2
                    and self.comparison_data.shape[1] >= 2
                ):
                    compare_x = self.comparison_data[:, 0]
                    compare_y = self.comparison_data[:, 1]
                else:
                    # If it's 1D, use pixel numbers as x
                    compare_y = self.comparison_data.copy()
                    compare_x = np.arange(len(compare_y))

                # Apply inversion if enabled (same as main data)
                # For comparison data, inversion means inverting the y-values around their max
                try:
                    if config.datainvert == 1:
                        # Invert the y-values (flip vertically)
                        max_val = np.max(compare_y) if len(compare_y) > 0 else 1
                        compare_y = max_val - compare_y + np.min(compare_y)
                except Exception as e:
                    print(f"Error inverting comparison data: {e}")

                # Apply mirroring if enabled (same as main data)
                try:
                    if getattr(config, "datamirror", 0) == 1:
                        compare_y = compare_y[::-1]
                        if compare_x is not None and len(compare_x) == len(compare_y):
                            compare_x = compare_x[::-1]
                except Exception as e:
                    print(f"Error mirroring comparison data: {e}")

                # Normalize comparison data so the minimum is at y=0 (baseline at zero intensity)
                try:
                    min_val = np.min(compare_y)
                    compare_y = compare_y - min_val
                except Exception as e:
                    print(f"Error normalizing comparison data: {e}")

                # Apply calibration to x-axis if in spectroscopy mode
                if (
                    config.spectroscopy_mode
                    and hasattr(default_calibration, "apply")
                    and callable(default_calibration.apply)
                ):
                    # If compare_x is already wavelengths, use as-is; otherwise convert from pixels
                    if compare_x.max() < 4000:  # Likely pixel numbers
                        compare_x = default_calibration.apply(compare_x.astype(int))

                CCDplot.a.plot(
                    compare_x, compare_y, color=self.compare_color, lw=1.0, alpha=0.8
                )
            except Exception as e:
                print(f"Error plotting comparison data: {e}")

        CCDplot.canvas.draw()

    def toggle_spectrum_colors(self):
        """Toggle the spectrum color background"""
        self.CCDplot.set_show_colors(self.show_colors.get())

    def collectmodefields(self):
        # collect mode - variables, widgets and traces associated with the collect mode
        collect_frame = widgets.CollapsibleTTK(self, title="Collection Options")
        collect_frame.pack(fill=tk.X, pady=5)

        # variables
        self.CONTvar = tk.IntVar()

        mode_row = ttk.Frame(collect_frame.sub_frame)
        mode_row.pack(fill=tk.X)

        self.roneshot = ttk.Radiobutton(
            mode_row,
            text="One shot",
            variable=self.CONTvar,
            value=0,
            command=lambda CONTvar=self.CONTvar: self.modeset(CONTvar),
        )
        self.roneshot.pack(side=tk.LEFT, padx=5)

        self.rcontinuous = ttk.Radiobutton(
            mode_row,
            text="Continuous",
            variable=self.CONTvar,
            value=1,
            command=lambda CONTvar=self.CONTvar: self.modeset(CONTvar),
        )
        self.rcontinuous.pack(side=tk.LEFT, padx=5)

        # set initial state
        self.CONTvar.set(config.AVGn[0])

        # average - variables, widgets and traces associated with the average slider
        avg_frame = ttk.Frame(collect_frame.sub_frame)
        avg_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        avg_row = ttk.Frame(avg_frame)
        avg_row.pack(fill=tk.X, pady=5)

        self.lavg = ttk.Label(avg_row, text="Averages")
        self.lavg.pack(side=tk.LEFT, padx=5)

        self.AVGscale = ttk.Scale(
            avg_row,
            from_=1,
            to=255,
            orient=tk.HORIZONTAL,
            length=200,
            command=self.AVGcallback,
        )
        self.AVGscale.pack(side=tk.RIGHT, padx=5)

        self.AVGlabel = ttk.Label(avg_row)
        self.AVGlabel.pack(side=tk.RIGHT, padx=5)

        self.AVGscale.set(config.AVGn[1])
        self.AVGlabel.config(text=str(config.AVGn[1]))

    def collectfields(self, SerQueue, progress_var):
        # collect and stop buttons
        button_container = ttk.Frame(self)
        button_container.pack(fill=tk.X, pady=5)

        self.buttonframe = ttk.Frame(button_container)
        self.buttonframe.pack(anchor=tk.CENTER)

        self.bcollect = ttk.Button(
            self.buttonframe,
            text="Collect",
            width=15,
            style="Accent.TButton",
            command=lambda panel=self, SerQueue=SerQueue, progress_var=progress_var: CCDserial.rxtx(
                panel, SerQueue, progress_var
            ),
        )
        self.bcollect.pack(side=tk.LEFT, padx=5)

        self.bstop = ttk.Button(
            self.buttonframe,
            text="Stop",
            width=15,
            command=lambda SerQueue=SerQueue: CCDserial.rxtxcancel(SerQueue),
            state=tk.DISABLED,
        )
        self.bstop.pack(side=tk.LEFT, padx=5)

        # progressbar
        self.progress = ttk.Progressbar(
            button_container,
            variable=progress_var,
            maximum=10,
            length=200,
        )
        self.progress.pack(pady=5)

    def plotmodefields(self, CCDplot):
        # plot mode - variables, widgets and traces associated with the plot mode
        plot_frame = widgets.CollapsibleTTK(self, title="Plot Options")
        plot_frame.pack(fill=tk.X, pady=5)

        # variables
        self.invert = tk.IntVar()
        self.balanced = tk.IntVar()
        self.show_colors = tk.IntVar()

        plot_label_row = ttk.Frame(plot_frame.sub_frame)
        plot_label_row.pack(fill=tk.X)

        self.cinvert = ttk.Checkbutton(
            plot_frame.sub_frame,
            text="Invert data",
            variable=self.invert,
            onvalue=1,
            offvalue=0,
        )
        self.cinvert.pack(anchor=tk.W)

        self.cbalance = ttk.Checkbutton(
            plot_frame.sub_frame,
            text="Balance even/odd pixels",
            variable=self.balanced,
            onvalue=1,
            offvalue=0,
            state=tk.DISABLED,
        )
        self.cbalance.pack(anchor=tk.W)

        # Mirror left/right
        self.mirror = tk.IntVar()
        self.cmirror = ttk.Checkbutton(
            plot_frame.sub_frame,
            text="Mirror data",
            variable=self.mirror,
            onvalue=1,
            offvalue=0,
        )
        self.cmirror.pack(anchor=tk.W)

        # Show colors checkbox
        self.cshowcolors = ttk.Checkbutton(
            plot_frame.sub_frame,
            text="Show colours",
            variable=self.show_colors,
            onvalue=1,
            offvalue=0,
            command=self.toggle_spectrum_colors,
        )
        self.cshowcolors.pack(anchor=tk.W)

        self.invert.trace_add(
            "write",
            lambda name, index, mode, invert=self.invert, CCDplot=CCDplot: self.RAWcallback(
                name, index, mode, invert, CCDplot
            ),
        )
        self.balanced.trace_add(
            "write",
            lambda name, index, mode, balanced=self.balanced, CCDplot=CCDplot: self.BALcallback(
                name, index, mode, balanced, CCDplot
            ),
        )
        # mirror trace
        self.mirror.trace_add(
            "write",
            lambda name, index, mode, mirror=self.mirror, CCDplot=CCDplot: self.MIRcallback(
                name, index, mode, mirror, CCDplot
            ),
        )

        # set initial state
        self.invert.set(config.datainvert)
        self.balanced.set(config.balanced)
        self.mirror.set(config.datamirror)
        self.show_colors.set(0)

        # Regression controls
        regression_frame = ttk.Frame(plot_frame.sub_frame)
        regression_frame.pack(fill=tk.X, pady=5)

        self.ph_checkbox_var = tk.IntVar(value=0)
        self.ph_check = ttk.Checkbutton(
            regression_frame,
            text="Regression",
            variable=self.ph_checkbox_var,
            onvalue=1,
            offvalue=0,
        )
        self.ph_check.pack(anchor=tk.W, padx=5)

        # Trace the checkbox
        self.ph_checkbox_var.trace_add(
            "write",
            lambda *args, CCDplot=CCDplot: (
                self._ph_check_changed(),
                self.updateplot(CCDplot),
            ),
        )

        # Placeholder slider
        slider_row = ttk.Frame(regression_frame)
        slider_row.pack(fill=tk.X, pady=5)

        self.lphslider = ttk.Label(slider_row, text="Strength")
        self.lphslider.pack(side=tk.LEFT, padx=5)

        self.ph_scale = ttk.Scale(
            slider_row,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            length=200,
            command=self._phslider_callback,
        )
        self.ph_scale.pack(side=tk.RIGHT, padx=5)

        self.ph_label = tk.Label(slider_row, text="0", fg="#ffffff")
        self.ph_label.pack(side=tk.RIGHT, padx=5)

        # Set initial enabled/disabled state based on the checkbox
        self._ph_check_changed()

        # Opacity slider
        opacity_row = ttk.Frame(regression_frame)
        opacity_row.pack(fill=tk.X, pady=5)

        self.opacity_scale = ttk.Scale(
            opacity_row,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            length=200,
            command=self._opacity_callback,
        )
        self.opacity_scale.pack(side=tk.RIGHT, padx=5)

        self.lopacity = ttk.Label(opacity_row, text="Raw opacity")
        self.lopacity.pack(side=tk.LEFT, padx=5)

        self.opacity_label = ttk.Label(opacity_row, text="1.00")
        self.opacity_label.pack(side=tk.RIGHT, padx=5)

        self.opacity_scale.set(100)

    def saveopenfields(self, CCDplot):
        # setup save/open buttons
        file_container = ttk.Frame(self)
        file_container.pack(fill=tk.X)

        self.fileframe = ttk.Frame(file_container)
        self.fileframe.pack(anchor=tk.CENTER, pady=5)

        self.bopen = ttk.Button(
            self.fileframe,
            text="Open",
            style="Accent.TButton",
            width=11,
            command=lambda self=self, CCDplot=CCDplot: CCDfiles.openfile(self, CCDplot),
        )
        self.bsave = ttk.Button(
            self.fileframe,
            text="Save",
            style="Accent.TButton",
            width=11,
            state=tk.DISABLED,
            command=lambda self=self: CCDfiles.savefile(self),
        )

        # Add calibration button next to save button
        self.bcalib = ttk.Button(
            self.fileframe,
            text="Calibration",
            style="Accent.TButton",
            width=11,
            command=self.open_calibration,
        )

        self.bopen.pack(side=tk.LEFT, padx=5)
        self.bsave.pack(side=tk.LEFT, padx=5)
        self.bcalib.pack(side=tk.LEFT, padx=5)

        # Now overlay the icon image on top of the buttons
        try:
            # Prefer a small palette icon if present, fallback to astrolens
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "assets"
            )
            preferred = os.path.join(base_dir, "palette.png")
            fallback = os.path.join(base_dir, "astrolens.png")
            icon_path = preferred if os.path.exists(preferred) else fallback

            if os.path.exists(icon_path):
                icon_image = Image.open(icon_path).convert("RGBA")

                # Make the icon solid black while preserving transparency
                try:
                    alpha = icon_image.getchannel("A")
                except Exception:
                    alpha = icon_image.convert("L")
                black_img = Image.new("RGBA", icon_image.size, (0, 0, 0, 255))
                icon_solid = Image.new("RGBA", icon_image.size, (0, 0, 0, 0))
                icon_solid.paste(black_img, (0, 0), mask=alpha)

                # Resize icon to reasonable size
                target_size = (16, 16)
                try:
                    resample = Image.Resampling.LANCZOS
                except Exception:
                    resample = Image.LANCZOS
                icon_image = icon_solid.resize(target_size, resample)
                icon_photo = ImageTk.PhotoImage(icon_image)

                # Place label with icon on top of the palette button
                self.icon_overlay = tk.Label(
                    self.b_icon,
                    image=icon_photo,
                    bg="#ffc200",  # Match Accent button color
                    bd=0,
                    cursor="hand2",  # Show hand cursor to indicate it's clickable
                )
                self.icon_overlay.image = icon_photo
                self.icon_overlay.place(relx=0.5, rely=0.5, anchor="center")

                # Make the overlay pass click events to the button underneath
                self.icon_overlay.bind("<Button-1>", lambda e: self.open_color_picker())
        except Exception as e:
            print(f"Could not create icon overlay: {e}")

    def open_calibration(self):
        """Open calibration window with proper callback reference"""
        default_calibration.open_calibration_window(
            self.master, on_apply_callback=self.CCDplot.replot_current_spectrum
        )

    def open_color_picker(self):
        """Open color picker window for plot customization"""
        # Check if color picker window already exists and is open
        if (
            hasattr(self, "color_window")
            and self.color_window
            and self.color_window.winfo_exists()
        ):
            self.color_window.lift()  # Bring existing window to front
            return

        # Create a new top-level window
        self.color_window = tk.Toplevel(self.master)
        self.color_window.title("Plot Colour Settings")
        self.color_window.resizable(False, False)

        # Set window size and center it on screen (adjusted for compare data section)
        window_width = 450
        window_height = 520
        screen_width = self.color_window.winfo_screenwidth()
        screen_height = self.color_window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.color_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Clean up reference when window is closed
        self.color_window.protocol(
            "WM_DELETE_WINDOW", lambda: self.close_color_window()
        )

        # Main plot color section
        ttk.Label(
            self.color_window, text="Main Plot Colour:", font=("Avenir", 10, "bold")
        ).pack(pady=5)

        main_color_frame = ttk.Frame(self.color_window)
        main_color_frame.pack(pady=5)

        # Color preview for main plot
        self.main_color_preview = tk.Canvas(
            main_color_frame,
            width=40,
            height=40,
            bg=self.main_plot_color,
            relief="solid",
            borderwidth=1,
        )
        self.main_color_preview.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            main_color_frame,
            text="Choose Colour",
            style="Accent.TButton",
            command=lambda: self.choose_plot_color("main", self.color_window),
        ).pack(side=tk.LEFT, padx=5)

        # Regression plot color section
        ttk.Label(
            self.color_window,
            text="Regression Line Colour:",
            font=("Avenir", 10, "bold"),
        ).pack(pady=5)

        regression_color_frame = ttk.Frame(self.color_window)
        regression_color_frame.pack(pady=5)

        # Color preview for regression
        self.regression_color_preview = tk.Canvas(
            regression_color_frame,
            width=40,
            height=40,
            bg=self.regression_color,
            relief="solid",
            borderwidth=1,
        )
        self.regression_color_preview.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            regression_color_frame,
            text="Choose Colour",
            style="Accent.TButton",
            command=lambda: self.choose_plot_color("regression", self.color_window),
        ).pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(self.color_window, orient="horizontal").pack(fill="x", pady=15)

        # Compare data section
        ttk.Label(
            self.color_window, text="Compare Data:", font=("Avenir", 10, "bold")
        ).pack(pady=5)

        compare_frame = ttk.Frame(self.color_window)
        compare_frame.pack(pady=5)

        # Compare data button
        ttk.Button(
            compare_frame,
            text="Load Data File",
            style="Accent.TButton",
            command=self.load_comparison_data,
        ).pack(side=tk.LEFT, padx=5)

        # Frame for filename display and remove button (dynamically shown)
        self.compare_info_frame = ttk.Frame(self.color_window)
        self.compare_info_frame.pack(pady=5)

        # Comparison color section (only shown when data is loaded)
        self.compare_color_section = ttk.Frame(self.color_window)

        # Update the display to show current comparison state
        self.update_compare_display()

        # Apply button
        ttk.Button(
            self.color_window,
            text="Apply & Close",
            style="Accent.TButton",
            command=lambda: self.close_color_window(),
        ).pack(pady=15)

    def load_comparison_data(self):
        """Load a .dat file for comparison"""
        from tkinter import filedialog
        import os

        filename = filedialog.askopenfilename(
            title="Select comparison data file",
            filetypes=[("Data files", "*.dat"), ("All files", "*.*")],
        )

        if filename:
            try:
                # Load the data using numpy
                data = np.loadtxt(filename)
                self.comparison_data = data
                self.comparison_filename = os.path.basename(filename)

                # Update the display
                self.update_compare_display()

                # Update the plot
                self.updateplot(self.CCDplot)
            except Exception as e:
                print(f"Error loading comparison data: {e}")

    def remove_comparison_data(self):
        """Remove the comparison data from the plot"""
        self.comparison_data = None
        self.comparison_filename = None

        # Update the display
        self.update_compare_display()

        # Update the plot
        self.updateplot(self.CCDplot)

    def update_compare_display(self):
        """Update the comparison data display in the color window"""
        if (
            not hasattr(self, "color_window")
            or not self.color_window
            or not self.color_window.winfo_exists()
        ):
            return

        # Clear existing widgets in compare info frame
        for widget in self.compare_info_frame.winfo_children():
            widget.destroy()

        # Clear existing widgets in compare color section
        for widget in self.compare_color_section.winfo_children():
            widget.destroy()

        if self.comparison_data is not None:
            # Show filename and remove button
            filename_label = ttk.Label(
                self.compare_info_frame,
                text=self.comparison_filename,
                font=("Avenir", 9),
            )
            filename_label.pack(side=tk.LEFT, padx=5)

            remove_btn = ttk.Button(
                self.compare_info_frame,
                text="✕",
                width=3,
                command=self.remove_comparison_data,
            )
            remove_btn.pack(side=tk.LEFT, padx=2)

            # Show comparison color picker
            self.compare_color_section.pack(pady=5)

            ttk.Label(
                self.compare_color_section,
                text="Comparison Data Colour:",
                font=("Avenir", 10, "bold"),
            ).pack(pady=5)

            compare_color_frame = ttk.Frame(self.compare_color_section)
            compare_color_frame.pack(pady=5)

            # Color preview for comparison
            self.compare_color_preview = tk.Canvas(
                compare_color_frame,
                width=40,
                height=40,
                bg=self.compare_color,
                relief="solid",
                borderwidth=1,
            )
            self.compare_color_preview.pack(side=tk.LEFT, padx=5)

            ttk.Button(
                compare_color_frame,
                text="Choose Colour",
                style="Accent.TButton",
                command=lambda: self.choose_plot_color("compare", self.color_window),
            ).pack(side=tk.LEFT, padx=5)

            # Force window to update its layout
            self.color_window.update_idletasks()
        else:
            # Hide the comparison color section if no data
            self.compare_color_section.pack_forget()
            # Force window to update its layout
            self.color_window.update_idletasks()

    def choose_plot_color(self, plot_type, window):
        """Open color chooser dialog and update preview"""
        if plot_type == "main":
            current_color = self.main_plot_color
        elif plot_type == "regression":
            current_color = self.regression_color
        else:  # compare
            current_color = self.compare_color

        color = colorchooser.askcolor(
            color=current_color, title=f"Choose {plot_type} color"
        )

        if color[1]:  # If user didn't cancel
            if plot_type == "main":
                self.main_plot_color = color[1]
                self.main_color_preview.config(bg=self.main_plot_color)
            elif plot_type == "regression":
                self.regression_color = color[1]
                self.regression_color_preview.config(bg=self.regression_color)
            else:  # compare
                self.compare_color = color[1]
                self.compare_color_preview.config(bg=self.compare_color)

            # Immediately update the plot with new color
            self.updateplot(self.CCDplot)
            # Close the window after color selection
            self.close_color_window()

    def close_color_window(self):
        """Close the color picker window and clean up reference"""
        if (
            hasattr(self, "color_window")
            and self.color_window
            and self.color_window.winfo_exists()
        ):
            self.color_window.destroy()
        self.color_window = None

    def zoom_mode(self):
        """Activate zoom mode on the plot"""
        if hasattr(self.CCDplot, "navigation_toolbar"):
            self.CCDplot.navigation_toolbar.zoom()

    def save_figure(self):
        """Open save dialog to save the figure"""
        if hasattr(self.CCDplot, "navigation_toolbar"):
            self.CCDplot.navigation_toolbar.save_figure()

    def updateplotfields(self, CCDplot):
        self.bupdate = ttk.Button(
            self,
            text="Update plot",
            command=lambda CCDplot=CCDplot: self.updateplot(CCDplot),
        )
        # setup an event on the invisible update-plot button with a callback this thread can invoke in the mainloop
        self.bupdate.event_generate("<ButtonPress>", when="tail")

        # commented out, it's needed to inject an event into the ttk.mainloop for updating the plot from the 'checkfordata' thread
        # self.bupdate.pack(fill=tk.X, padx=5)

    def _phslider_callback(self, val):
        """Internal callback for the placeholder slider to update the label."""
        try:
            v = float(val)
        except Exception:
            v = 0.0
        # Map slider (0..100) to smoothing factor. Make mapping finer at low
        # slider values by using a divisor of 1000 instead of 500.
        smooth = v / 1000.0
        # Show smoothing value with a bit more precision so weak smoothing is visible
        try:
            self.ph_label.config(text=f"{smooth:.4f}")
        except Exception:
            # fallback to integer display
            self.ph_label.config(text=str(int(round(v))))
        # If regression is enabled, update the plot so changes take effect immediately
        try:
            if (
                getattr(self, "ph_checkbox_var", None)
                and self.ph_checkbox_var.get() == 1
            ):
                try:
                    self.updateplot(self.CCDplot)
                except Exception:
                    pass
        except Exception:
            pass

    def _ph_check_changed(self):
        """Enable or disable the placeholder slider based on the checkbox state

        Also dim the label color when disabled to give a visual cue.
        """
        enabled = bool(self.ph_checkbox_var.get())
        if enabled:
            # enable the scale
            try:
                self.ph_scale.state(["!disabled"])
            except Exception:
                try:
                    self.ph_scale.configure(state=tk.NORMAL)
                except Exception:
                    pass
            # bright label
            try:
                self.ph_label.config(fg="#ffffff")
            except Exception:
                pass
        else:
            # disable the scale
            try:
                self.ph_scale.state(["disabled"])
            except Exception:
                try:
                    self.ph_scale.configure(state=tk.DISABLED)
                except Exception:
                    pass
            # dim label
            try:
                self.ph_label.config(fg="#888888")
            except Exception:
                pass

    def _opacity_callback(self, val):
        """Callback for the opacity slider: update label and redraw plot."""
        try:
            v = float(val)
        except Exception:
            v = 100.0
        alpha = max(0.0, min(1.0, v / 100.0))
        try:
            self.opacity_label.config(text=f"{alpha:.2f}")
        except Exception:
            pass

        # Redraw the plot to apply new opacity
        try:
            self.updateplot(self.CCDplot)
        except Exception:
            pass

    def callback(self):
        self.bopen.config(state=tk.DISABLED)
        return ()

    def aboutbutton(self):
        # Create a frame to hold icon buttons
        about_container = ttk.Frame(self)
        about_container.pack(fill=tk.X, pady=5)

        button_frame = ttk.Frame(about_container)
        button_frame.pack(anchor=tk.CENTER)

        # Create three icon buttons
        self.b_icon = ttk.Button(
            button_frame,
            text="",
            style="Accent.TButton",
            width=3,
            command=self.open_color_picker,
        )
        self.b_icon.pack(side=tk.LEFT, padx=2)

        self.b_zoom = ttk.Button(
            button_frame,
            text="",
            style="Accent.TButton",
            width=3,
            command=self.save_figure,
        )
        self.b_zoom.pack(side=tk.LEFT, padx=2)

        self.b_save_img = ttk.Button(
            button_frame,
            text="",
            style="Accent.TButton",
            width=3,
            command=self.zoom_mode,
        )
        self.b_save_img.pack(side=tk.LEFT, padx=2)

        # Add icon overlays to the buttons
        try:
            from PIL import Image, ImageTk
            import os

            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "assets"
            )
            preferred = os.path.join(base_dir, "palette.png")
            fallback = os.path.join(base_dir, "astrolens.png")
            icon_path = preferred if os.path.exists(preferred) else fallback

            if os.path.exists(icon_path):
                icon_image = Image.open(icon_path).convert("RGBA")

                # Make the icon solid black while preserving transparency
                try:
                    alpha = icon_image.getchannel("A")
                except Exception:
                    alpha = icon_image.convert("L")
                black_img = Image.new("RGBA", icon_image.size, (0, 0, 0, 255))
                icon_solid = Image.new("RGBA", icon_image.size, (0, 0, 0, 0))
                icon_solid.paste(black_img, (0, 0), mask=alpha)

                # Resize icon to reasonable size
                target_size = (16, 16)
                try:
                    resample = Image.Resampling.LANCZOS
                except Exception:
                    resample = Image.LANCZOS
                icon_image = icon_solid.resize(target_size, resample)
                icon_photo = ImageTk.PhotoImage(icon_image)

                # Place label with icon on palette button
                self.icon_overlay = tk.Label(
                    self.b_icon,
                    image=icon_photo,
                    bg="#ffc200",
                    bd=0,
                    cursor="hand2",
                )
                self.icon_overlay.image = icon_photo
                self.icon_overlay.place(relx=0.5, rely=0.5, anchor="center")
                self.icon_overlay.bind("<Button-1>", lambda e: self.open_color_picker())

                # Place icon on zoom button (use save.png)
                save_icon_path = os.path.join(base_dir, "save.png")
                if os.path.exists(save_icon_path):
                    save_icon_image = Image.open(save_icon_path).convert("RGBA")
                    # Make black
                    try:
                        save_alpha = save_icon_image.getchannel("A")
                    except Exception:
                        save_alpha = save_icon_image.convert("L")
                    save_black_img = Image.new(
                        "RGBA", save_icon_image.size, (0, 0, 0, 255)
                    )
                    save_icon_solid = Image.new(
                        "RGBA", save_icon_image.size, (0, 0, 0, 0)
                    )
                    save_icon_solid.paste(save_black_img, (0, 0), mask=save_alpha)
                    save_icon_resized = save_icon_solid.resize(target_size, resample)
                    icon_photo_zoom = ImageTk.PhotoImage(save_icon_resized)
                else:
                    icon_photo_zoom = ImageTk.PhotoImage(
                        icon_solid.resize(target_size, resample)
                    )

                self.icon_overlay_zoom = tk.Label(
                    self.b_zoom,
                    image=icon_photo_zoom,
                    bg="#ffc200",
                    bd=0,
                    cursor="hand2",
                )
                self.icon_overlay_zoom.image = icon_photo_zoom
                self.icon_overlay_zoom.place(relx=0.5, rely=0.5, anchor="center")
                self.icon_overlay_zoom.bind("<Button-1>", lambda e: self.save_figure())

                # Place icon on save_img button (use lens.png)
                lens_icon_path = os.path.join(base_dir, "lens.png")
                if os.path.exists(lens_icon_path):
                    lens_icon_image = Image.open(lens_icon_path).convert("RGBA")
                    # Make black
                    try:
                        lens_alpha = lens_icon_image.getchannel("A")
                    except Exception:
                        lens_alpha = lens_icon_image.convert("L")
                    lens_black_img = Image.new(
                        "RGBA", lens_icon_image.size, (0, 0, 0, 255)
                    )
                    lens_icon_solid = Image.new(
                        "RGBA", lens_icon_image.size, (0, 0, 0, 0)
                    )
                    lens_icon_solid.paste(lens_black_img, (0, 0), mask=lens_alpha)
                    lens_icon_resized = lens_icon_solid.resize(target_size, resample)
                    icon_photo_save = ImageTk.PhotoImage(lens_icon_resized)
                else:
                    icon_photo_save = ImageTk.PhotoImage(
                        icon_solid.resize(target_size, resample)
                    )

                self.icon_overlay_save = tk.Label(
                    self.b_save_img,
                    image=icon_photo_save,
                    bg="#ffc200",
                    bd=0,
                    cursor="hand2",
                )
                self.icon_overlay_save.image = icon_photo_save
                self.icon_overlay_save.place(relx=0.5, rely=0.5, anchor="center")
                self.icon_overlay_save.bind("<Button-1>", lambda e: self.zoom_mode())
        except Exception as e:
            print(f"Could not create icon overlays: {e}")

        self.bhelp = ttk.Button(
            button_frame,
            text="Help",
            width=11,
            command=self.open_help_url,
        )
        self.bhelp.pack(side=tk.LEFT, padx=5)

        # Add AstroLens logo below the buttons
        try:
            from PIL import Image, ImageTk
            import os

            # Get the path to the PNG file
            logo_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "assets", "astrolens.png"
            )

            if os.path.exists(logo_path):
                logo_image = Image.open(logo_path)

                # Calculate proper aspect ratio resize
                target_width = 350
                aspect_ratio = logo_image.width / logo_image.height
                target_height = int(target_width / aspect_ratio)

                logo_image = logo_image.resize(
                    (target_width, target_height), Image.Resampling.LANCZOS
                )
                logo_photo = ImageTk.PhotoImage(logo_image)

                self.logo_label = ttk.Label(about_container, image=logo_photo)
                self.logo_label.image = logo_photo  # Keep a reference
                self.logo_label.pack(pady=(40, 5))
        except Exception as e:
            print(f"Could not load logo: {e}")

    def open_help_url(self):
        """Open the help URL in the default browser"""
        try:
            webbrowser.open("https://www.astrolens.net/pyspec-help")
        except Exception as e:
            print(f"Failed to open browser: {e}")
