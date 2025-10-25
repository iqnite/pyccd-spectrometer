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
from tkinter import ttk
import numpy as np
import serial
import math

from spectrometer import config, CCDhelp, CCDserial, CCDfiles
from spectrometer.calibration import default_calibration


class BuildPanel(ttk.Frame):
    def __init__(self, master, CCDplot, SerQueue):
        # geometry-rows for packing the grid
        mode_row = 5
        device_row = 15
        shicg_row = 25
        continuous_row = 35
        avg_row = 45
        collect_row = 55
        plotmode_row = 65
        save_row = 75
        update_row = 85
        progress_var = tk.IntVar()

        super().__init__(master)

        # Store CCDplot reference for callbacks
        self.CCDplot = CCDplot

        # Create all widgets and space between them
        self.mode_fields(mode_row)
        # insert vertical space
        self.grid_rowconfigure(mode_row + 1, minsize=20)
        self.devicefields(device_row)
        # insert vertical space
        self.grid_rowconfigure(device_row + 4, minsize=30)
        self.CCDparamfields(shicg_row)
        # insert vertical space
        self.grid_rowconfigure(shicg_row + 4, minsize=30)
        self.collectmodefields(continuous_row)
        self.avgfields(avg_row)
        # insert vertical space
        self.grid_rowconfigure(avg_row + 2, minsize=30)
        self.collectfields(collect_row, SerQueue, progress_var)
        # vertical space
        self.grid_rowconfigure(collect_row + 2, minsize=30)
        self.plotmodefields(plotmode_row, CCDplot)
        self.saveopenfields(save_row, CCDplot)
        self.updateplotfields(update_row, CCDplot)
        # vertical space
        self.grid_rowconfigure(update_row + 2, minsize=20)
        self.aboutbutton(update_row + 3)

    def mode_fields(self, mode_row):
        """Add spectroscopy mode toggle"""
        self.mode_frame = ttk.Frame(self)
        self.mode_frame.grid(row=mode_row, columnspan=3, pady=10)

        ttk.Label(
            self.mode_frame, text="Operation Mode:", font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=5)

        self.mode_var = tk.IntVar(value=0)  # 0 = Regular, 1 = Spectroscopy

        self.r_regular = ttk.Radiobutton(
            self.mode_frame,
            text="Regular Mode",
            variable=self.mode_var,
            value=0,
            command=self.mode_changed,
        )
        self.r_regular.pack(side=tk.LEFT, padx=5)

        self.r_spectroscopy = ttk.Radiobutton(
            self.mode_frame,
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

    def devicefields(self, device_row):
        # device setup - variables, widgets and traces associated with the device entrybox
        # variables
        self.device_address = tk.StringVar()
        self.device_status = tk.StringVar()
        self.device_statuscolor = tk.StringVar()
        # widgets
        self.ldevice = ttk.Label(self, text="COM-device:")
        self.ldevice.grid(column=0, row=device_row)
        self.edevice = ttk.Entry(self, textvariable=self.device_address, justify="left")
        self.edevice.grid(column=1, row=device_row)
        self.ldevicestatus = tk.Label(
            self, textvariable=self.device_status, fg="#ffffff"
        )
        # setup trace to check if the device exists
        self.device_address.trace_add(
            "write",
            lambda name, index, mode, Device=self.device_address, status=self.device_status, colr=self.ldevicestatus: self.DEVcallback(
                name, index, mode, Device, status, colr
            ),
        )
        self.device_address.set(config.port)
        self.ldevicestatus.grid(columnspan=2, row=device_row + 1)
        # firmware selection
        self.lfirmware = ttk.Label(self, text="Firmware:")
        self.lfirmware.grid(column=0, row=device_row + 2)
        self.firmware_type = tk.StringVar(value="STM32F40x")
        self.firmware_dropdown = ttk.Combobox(
            self,
            textvariable=self.firmware_type,
            values=["STM32F40x", "STM32F103"],
            state="readonly",
        )
        self.firmware_dropdown.grid(column=1, row=device_row + 2)
        self.firmware_type.trace_add("write", self.update_firmware)
        # help button
        self.bhdev = ttk.Button(
            self, text="?", command=lambda helpfor=0: CCDhelp.helpme(helpfor)
        )
        self.bhdev.grid(row=device_row, column=3)

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

    def CCDparamfields(self, shicg_row):
        # CCD parameters - variables, widgets and traces associated with setting exposure
        # variables
        self.SH = tk.StringVar()
        self.ICG = tk.StringVar()
        self.tint_status = tk.StringVar()
        self.tint_statuscolor = tk.StringVar()
        self.tint_value = tk.StringVar()  # For exposure time numeric input
        self.tint_unit = tk.StringVar(value="ms")  # Default unit

        # Exposure time input directly gridded for alignment
        self.l_exposure = ttk.Label(self, text="Exposure Time:")
        self.l_exposure.grid(column=0, row=shicg_row)
        self.e_tint = ttk.Entry(
            self, textvariable=self.tint_value, justify="left", width=10
        )
        self.e_tint.grid(column=1, row=shicg_row)
        self.unit_dropdown = ttk.Combobox(
            self,
            textvariable=self.tint_unit,
            values=["us", "ms", "s", "min"],
            state="readonly",
            width=5,
        )
        self.unit_dropdown.grid(column=2, row=shicg_row)

        # Original SH/ICG fields (keep for display/override, but auto-update)
        self.lSH = ttk.Label(self, text="SH-period:")
        self.lSH.grid(column=0, row=shicg_row + 1)
        self.eSH = ttk.Entry(self, textvariable=self.SH, justify="left")
        self.eSH.grid(column=1, row=shicg_row + 1)

        self.lICG = ttk.Label(self, text="ICG-period:")
        self.lICG.grid(column=0, row=shicg_row + 2)
        self.eICG = ttk.Entry(self, textvariable=self.ICG, justify="left")
        self.eICG.grid(column=1, row=shicg_row + 2)

        # Status labels
        self.lccdstatus = tk.Label(self, textvariable=self.tint_status)
        self.lccdstatus.grid(columnspan=2, row=shicg_row + 3)
        self.ltint = tk.Label(self, textvariable=self.tint_statuscolor)
        self.ltint.grid(columnspan=2, row=shicg_row + 4)

        # Help button
        self.bhccd = ttk.Button(
            self, text="?", command=lambda helpfor=1: CCDhelp.helpme(helpfor)
        )
        self.bhccd.grid(row=shicg_row, column=3)

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
                status.set("Device exist")
                ser.close()
                colr.configure(fg="#ffffff")
            except serial.SerialException:
                status.set("Device doesn't exist")
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

        # Set axis limits based on mode - FIXED: Normal direction for spectroscopy
        if (
            config.spectroscopy_mode
            and hasattr(default_calibration, "apply")
            and callable(default_calibration.apply)
        ):
            # Normal direction for spectroscopy: lower wavelengths on left, higher on right
            CCDplot.a.set_xlim(x_values[0], x_values[-1])
        else:
            # Normal axis for regular mode
            CCDplot.a.set_xlim(x_values[0], x_values[-1])

        # plot intensities
        if config.datainvert == 1:
            CCDplot.a.plot(x_values, config.pltData16)
            CCDplot.a.set_ylabel("Intensity")
            CCDplot.a.set_xlabel(x_label)
            # Set Y-axis range for intensity plot
            CCDplot.a.set_ylim(-10, 2250)
        else:
            # plot raw data
            CCDplot.a.plot(x_values, config.rxData16)
            CCDplot.a.set_ylabel("ADCcount")
            CCDplot.a.set_xlabel(x_label)
            # Set Y-axis range for raw data plot
            CCDplot.a.set_ylim(-10, 4095)

        # Update spectrum background
        self.CCDplot.set_show_colors(self.show_colors.get())

        CCDplot.canvas.draw()

    def toggle_spectrum_colors(self):
        """Toggle the spectrum color background"""
        self.CCDplot.set_show_colors(self.show_colors.get())

    def collectmodefields(self, continuous_row):
        # collect mode - variables, widgets and traces associated with the collect mode
        # variables
        self.CONTvar = tk.IntVar()
        # widgets
        self.lcontinuous = ttk.Label(self, text="Collection mode:")
        self.lcontinuous.grid(column=0, row=continuous_row)
        self.roneshot = ttk.Radiobutton(
            self,
            text="One shot",
            variable=self.CONTvar,
            value=0,
            command=lambda CONTvar=self.CONTvar: self.modeset(CONTvar),
        )
        self.roneshot.grid(column=1, row=continuous_row)
        self.rcontinuous = ttk.Radiobutton(
            self,
            text="Continuous",
            variable=self.CONTvar,
            value=1,
            command=lambda CONTvar=self.CONTvar: self.modeset(CONTvar),
        )
        self.rcontinuous.grid(column=1, row=continuous_row + 1)
        # help button
        self.bhcon = ttk.Button(
            self, text="?", command=lambda helpfor=2: CCDhelp.helpme(helpfor)
        )
        self.bhcon.grid(row=continuous_row, column=3)
        # set initial state
        self.CONTvar.set(config.AVGn[0])

    def avgfields(self, avg_row):
        # average - variables, widgets and traces associated with the average slider
        # widgets
        self.lavg = ttk.Label(self, text="Averages:")
        self.lavg.grid(column=0, row=avg_row)
        self.AVGscale = ttk.Scale(
            self,
            from_=1,
            to=255,
            orient=tk.HORIZONTAL,
            length=200,
            command=self.AVGcallback,
        )
        self.AVGscale.grid(column=1, row=avg_row)
        self.AVGlabel = ttk.Label(self)
        self.AVGlabel.grid(column=2, row=avg_row)
        self.AVGscale.set(config.AVGn[1])
        self.AVGlabel.config(text=str(config.AVGn[1]))
        # help button
        self.bhavg = ttk.Button(
            self, text="?", command=lambda helpfor=3: CCDhelp.helpme(helpfor)
        )
        self.bhavg.grid(row=avg_row, column=3)

    def collectfields(self, collect_row, SerQueue, progress_var):
        # collect and stop buttons
        self.bcollect = ttk.Button(
            self,
            text="Collect",
            width=15,
            style="Accent.TButton",
            command=lambda panel=self, SerQueue=SerQueue, progress_var=progress_var: CCDserial.rxtx(
                panel, SerQueue, progress_var
            ),
        )
        self.bcollect.grid(row=collect_row, columnspan=2, sticky="EW", padx=5)
        self.bstop = ttk.Button(
            self,
            text="Stop",
            width=15,
            command=lambda SerQueue=SerQueue: CCDserial.rxtxcancel(SerQueue),
            state=tk.DISABLED,
        )
        self.bstop.grid(row=collect_row + 1, columnspan=2, sticky="EW", padx=5, pady=5)
        # help button
        self.bhcol = ttk.Button(
            self, text="?", command=lambda helpfor=4: CCDhelp.helpme(helpfor)
        )
        self.bhcol.grid(row=collect_row, column=3)
        # progressbar
        self.progress = ttk.Progressbar(
            self, variable=progress_var, maximum=10, length=200
        )
        self.progress.grid(row=collect_row + 2, columnspan=2, sticky="EW", padx=5)

    def plotmodefields(self, plotmode_row, CCDplot):
        # plot mode - variables, widgets and traces associated with the plot mode
        # variables
        self.invert = tk.IntVar()
        self.balanced = tk.IntVar()
        self.show_colors = tk.IntVar()

        # widgets
        self.lplot = ttk.Label(self, text="Plot mode:")
        self.lplot.grid(column=0, row=plotmode_row)
        self.cinvert = ttk.Checkbutton(
            self, text="Invert data", variable=self.invert, onvalue=1, offvalue=0
        )
        self.cinvert.grid(column=1, row=plotmode_row)
        self.cbalance = ttk.Checkbutton(
            self,
            text="Balance even/odd pixels",
            variable=self.balanced,
            onvalue=1,
            offvalue=0,
            state=tk.DISABLED,
        )
        self.cbalance.grid(column=1, row=plotmode_row + 1)

        # Show colors checkbox
        self.cshowcolors = ttk.Checkbutton(
            self,
            text="Show colours",
            variable=self.show_colors,
            onvalue=1,
            offvalue=0,
            command=self.toggle_spectrum_colors,
        )
        self.cshowcolors.grid(column=1, row=plotmode_row + 2)

        # setup traces to update the plot
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

        # set initial state
        self.invert.set(config.datainvert)
        self.balanced.set(config.balanced)
        self.show_colors.set(0)

        # help button
        self.bhplo = ttk.Button(
            self, text="?", command=lambda helpfor=6: CCDhelp.helpme(helpfor)
        )
        self.bhplo.grid(row=plotmode_row, column=3)

    def saveopenfields(self, save_row, CCDplot):
        # setup save/open buttons
        self.fileframe = ttk.Frame(self)
        self.fileframe.grid(row=save_row, columnspan=2)
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

        self.bopen.pack(side=tk.LEFT)
        self.bsave.pack(side=tk.LEFT, padx=(5, 0))
        self.bcalib.pack(
            side=tk.LEFT, padx=(5, 0)
        )  # Add some padding to separate from save button

        # help button
        self.bhsav = ttk.Button(
            self, text="?", command=lambda helpfor=5: CCDhelp.helpme(helpfor)
        )
        self.bhsav.grid(row=save_row, column=3)

    def open_calibration(self):
        """Open calibration window with proper callback reference"""
        default_calibration.open_calibration_window(
            self.master, on_apply_callback=self.CCDplot.replot_current_spectrum
        )

    def updateplotfields(self, update_row, CCDplot):
        self.bupdate = ttk.Button(
            self,
            text="Update plot",
            command=lambda CCDplot=CCDplot: self.updateplot(CCDplot),
        )
        # setup an event on the invisible update-plot button with a callback this thread can invoke in the mainloop
        self.bupdate.event_generate("<ButtonPress>", when="tail")

        # commented out, it's needed to inject an event into the ttk.mainloop for updating the plot from the 'checkfordata' thread
        # self.bupdate.grid(row=update_row, columnspan=3, sticky="EW", padx=5)

    def callback(self):
        self.bopen.config(state=tk.DISABLED)
        return ()

    def aboutbutton(self, about_row):
        self.babout = ttk.Button(
            self,
            text="About",
            command=lambda helpfor=10: CCDhelp.helpme(helpfor),
        )
        self.babout.grid(row=about_row, columnspan=3, sticky="EW", padx=5)
