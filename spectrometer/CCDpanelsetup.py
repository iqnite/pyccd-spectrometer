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
from tkinter import ttk, colorchooser, messagebox
import numpy as np
import serial
import math
import webbrowser
import json
import os

from spectrometer import config, CCDhelp, CCDserial, CCDfiles
from spectrometer.calibration import default_calibration
from utils import plotgraph

# COM settings file
COM_SETTINGS_FILE = "com_settings.json"


class BuildPanel(ttk.Frame):
    def __init__(self, master, CCDplot, SerQueue):
        # geometry-rows for packing the grid
        mode_row = 14
        device_row = 24
        shicg_row = 34
        continuous_row = 44
        avg_row = 54
        collect_row = 64
        plotmode_row = 74
        save_row = 84
        update_row = 94
        progress_var = tk.IntVar()

        super().__init__(master)

        # Store CCDplot reference for callbacks
        self.CCDplot = CCDplot
        
        # Initialize plot colors
        self.main_plot_color = "#1f77b4"  # Default matplotlib blue
        self.regression_color = "#d62728"  # Default red
        self.compare_color = "#2ca02c"  # Default green for comparison data
        self.emission_line_color = "red"  # Default red for emission lines (when not matched)
        self.emission_color_button = None
        self.emission_color_preview = None
        
        # Initialize comparison data storage
        self.comparison_data = None
        self.comparison_filename = None
        
        # Initialize baseline data storage
        self.baseline_data = None
        self.baseline_subtract_enabled = False

        # Create all widgets and space between them
        self.header_fields()
        self.grid_rowconfigure(1, minsize=25)  # Add space after header
        self.mode_fields(mode_row)
        # insert vertical space
        self.grid_rowconfigure(mode_row + 1, minsize=20)
        self.devicefields(device_row)
        # insert vertical space
        self.grid_rowconfigure(device_row + 1, minsize=30)
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

    def header_fields(self):
        """Add header, logo, and close button"""
        # Add AstroLens logo on the left
        try:
            from PIL import Image, ImageTk
            import os
            
            # Get the path to the PNG file
            logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "astrolens.png")
            
            if os.path.exists(logo_path):
                logo_image = Image.open(logo_path)
                
                # Calculate proper aspect ratio resize for header
                target_height = 45  # Increased from 30 for larger logo
                aspect_ratio = logo_image.width / logo_image.height
                target_width = int(target_height * aspect_ratio)
                
                logo_image = logo_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_image)
                
                self.logo_label = ttk.Label(self, image=logo_photo)
                self.logo_label.image = logo_photo  # Keep a reference
                self.logo_label.grid(row=0, column=0, pady=10, padx=(5, 0), sticky="w")
        except Exception as e:
            print(f"Could not load logo: {e}")
        
        self.lheader = ttk.Label(
            self,
            text="pySPEC",
            font=("Avenir", 16, "bold"),
            foreground="#ffc200",
        )
        self.lheader.grid(row=0, column=1, pady=10, padx=5, sticky="e")
        
        # Create circular close button with high resolution
        from PIL import Image, ImageDraw, ImageFont
        
        button_size = 30
        scale = 4  # Render at 4x resolution for smooth edges
        high_res_size = button_size * scale
        
        # Create high-resolution image
        self.button_img = Image.new('RGBA', (high_res_size, high_res_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.button_img, 'RGBA')
        
        # Draw smooth circle
        draw.ellipse([0, 0, high_res_size-1, high_res_size-1], fill='#ffc200')
        
        # Draw X text - use simple X instead of unicode
        try:
            font = ImageFont.truetype("arial.ttf", int(16 * scale))
        except:
            try:
                font = ImageFont.truetype("Arial.ttf", int(16 * scale))
            except:
                font = None
        
        text = "X"
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (high_res_size - text_width) // 2 - bbox[0]
            text_y = (high_res_size - text_height) // 2 - bbox[1]
            draw.text((text_x, text_y), text, fill='black', font=font)
        else:
            # Fallback: draw X as two lines
            padding = high_res_size // 4
            draw.line([(padding, padding), (high_res_size-padding, high_res_size-padding)], fill='black', width=scale*2)
            draw.line([(high_res_size-padding, padding), (padding, high_res_size-padding)], fill='black', width=scale*2)
        
        # Scale down for smooth anti-aliased result
        self.button_img = self.button_img.resize((button_size, button_size), Image.Resampling.LANCZOS)
        self.button_photo = ImageTk.PhotoImage(self.button_img)
        
        # Create hover version (darker)
        self.button_img_hover = Image.new('RGBA', (high_res_size, high_res_size), (0, 0, 0, 0))
        draw_hover = ImageDraw.Draw(self.button_img_hover, 'RGBA')
        draw_hover.ellipse([0, 0, high_res_size-1, high_res_size-1], fill='#e6ad00')
        
        if font:
            draw_hover.text((text_x, text_y), text, fill='black', font=font)
        else:
            draw_hover.line([(padding, padding), (high_res_size-padding, high_res_size-padding)], fill='black', width=scale*2)
            draw_hover.line([(high_res_size-padding, padding), (padding, high_res_size-padding)], fill='black', width=scale*2)
        
        self.button_img_hover = self.button_img_hover.resize((button_size, button_size), Image.Resampling.LANCZOS)
        self.button_photo_hover = ImageTk.PhotoImage(self.button_img_hover)
        
        # Get background color
        try:
            style = ttk.Style()
            bg_color = style.lookup('TFrame', 'background')
            if not bg_color:
                bg_color = '#1c1c1c'
        except:
            bg_color = '#1c1c1c'
        
        # Create canvas with the button image
        self.bclose = tk.Canvas(
            self,
            width=button_size,
            height=button_size,
            highlightthickness=0,
            bg=bg_color
        )
        
        self.button_image_id = self.bclose.create_image(
            button_size//2, button_size//2,
            image=self.button_photo
        )
        
        # Bind hover and click events
        self.bclose.bind("<Enter>", self.on_close_hover)
        self.bclose.bind("<Leave>", self.on_close_leave)
        self.bclose.bind("<Button-1>", lambda e, root=self.master: root.destroy())
        self.bclose.config(cursor="hand2")
        
        self.bclose.grid(row=0, column=2, pady=10, padx=(0, 5))
    
    def on_close_hover(self, event):
        """Change color on hover"""
        self.bclose.itemconfig(self.button_image_id, image=self.button_photo_hover)
    
    def on_close_leave(self, event):
        """Restore color when not hovering"""
        self.bclose.itemconfig(self.button_image_id, image=self.button_photo)

    def mode_fields(self, mode_row):
        """Add spectroscopy mode toggle"""
        ttk.Label(self, text="Operation Mode:").grid(
            row=mode_row, column=0, padx=5, sticky="e"
        )

        self.mode_var = tk.IntVar(value=0)  # 0 = Regular, 1 = Spectroscopy

        self.r_regular = ttk.Radiobutton(
            self,
            text="Regular Mode",
            variable=self.mode_var,
            value=0,
            command=self.mode_changed,
        )
        self.r_regular.grid(row=mode_row, column=1, padx=5, sticky="w")

        self.r_spectroscopy = ttk.Radiobutton(
            self,
            text="Spectroscopy Mode",
            variable=self.mode_var,
            value=1,
            command=self.mode_changed,
        )
        self.r_spectroscopy.grid(row=mode_row + 1, column=1, padx=5, sticky="w")

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

        # Remove any existing markers because axis scaling just changed
        if hasattr(self, 'CCDplot') and hasattr(self.CCDplot, 'clear_markers'):
            self.CCDplot.clear_markers()

        # Update emission line color control availability
        self.update_emission_color_controls()

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
        # Load saved COM settings first
        self.load_com_settings()
        
        # variables
        self.device_address = tk.StringVar()
        self.device_status = tk.StringVar()
        self.device_statuscolor = tk.StringVar()
        
        # widgets
        self.ldevice = ttk.Label(self, text="COM-device:")
        self.ldevice.grid(column=0, row=device_row, sticky="e")
        
        # Frame to hold entry and save button
        device_frame = ttk.Frame(self)
        device_frame.grid(column=1, row=device_row, sticky="w", padx=5)
        
        self.edevice = ttk.Entry(device_frame, textvariable=self.device_address, justify="left", width=15)
        self.edevice.pack(side=tk.LEFT)
        
        # Add save icon button
        self.add_com_save_button(device_frame)
        
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
        self.ldevicestatus.grid(column=1, row=device_row + 1, sticky="w", padx=5)
        # firmware selection
        self.lfirmware = ttk.Label(self, text="Firmware:")
        self.lfirmware.grid(column=0, row=device_row + 2, sticky="e", pady=5)
        # Use saved firmware if available
        default_firmware = getattr(config, 'saved_firmware', 'STM32F40x')
        self.firmware_type = tk.StringVar(value=default_firmware)
        self.firmware_dropdown = ttk.Combobox(
            self,
            textvariable=self.firmware_type,
            values=["STM32F40x", "STM32F103"],
            state="readonly",
        )
        self.firmware_dropdown.grid(column=1, row=device_row + 2, padx=5, sticky="w")
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
        self.l_exposure.grid(column=0, row=shicg_row, pady=5, sticky="e")
        self.f_exposure = ttk.Frame(self)
        self.f_exposure.grid(column=1, row=shicg_row, pady=5, padx=5, sticky="w")
        self.e_tint = ttk.Entry(
            self.f_exposure, textvariable=self.tint_value, justify="left", width=10
        )
        self.e_tint.pack(side=tk.LEFT, anchor="w")
        self.unit_dropdown = ttk.Combobox(
            self.f_exposure,
            textvariable=self.tint_unit,
            values=["us", "ms", "s", "min"],
            state="readonly",
            width=5,
        )
        self.unit_dropdown.pack(side=tk.LEFT, padx=5, anchor="w")

        # Original SH/ICG fields (keep for display/override, but auto-update)
        self.lSH = ttk.Label(self, text="SH-period:")
        self.lSH.grid(column=0, row=shicg_row + 1, pady=5, sticky="e")
        self.eSH = ttk.Entry(self, textvariable=self.SH, justify="left")
        self.eSH.grid(column=1, row=shicg_row + 1, padx=5, pady=5, sticky="w")

        self.lICG = ttk.Label(self, text="ICG-period:")
        self.lICG.grid(column=0, row=shicg_row + 2, pady=5, sticky="e")
        self.eICG = ttk.Entry(self, textvariable=self.ICG, justify="left")
        self.eICG.grid(column=1, row=shicg_row + 2, padx=5, pady=5, sticky="w")

        # Status labels
        self.lccdstatus = tk.Label(self, textvariable=self.tint_status)
        self.lccdstatus.grid(column=1, row=shicg_row + 3, pady=5, sticky="w")
        self.ltint = tk.Label(self, textvariable=self.tint_statuscolor)
        self.ltint.grid(column=1, row=shicg_row + 4, pady=5, sticky="w")

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

        # Capture current x-limits early so we can restore user zoom after redraw
        try:
            prev_xlim = tuple(self.CCDplot.a.get_xlim()) if hasattr(self.CCDplot, "a") and self.CCDplot.a is not None else None
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
            data = config.pltData16.copy()
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
            
            # Apply baseline subtraction if enabled
            if self.baseline_subtract_enabled and self.baseline_data is not None:
                try:
                    # Ensure baseline data has same length as current data
                    if len(self.baseline_data) == len(data):
                        data = data.astype(float) - self.baseline_data.astype(float)
                except Exception as e:
                    print(f"Baseline subtraction error: {e}")

            # Plot raw/intensity data directly
            CCDplot.a.plot(x_values, data, alpha=alpha, color=self.main_plot_color)
            CCDplot.a.set_ylabel("Intensity")
            CCDplot.a.set_xlabel(x_label)
            # Set Y-axis range for intensity plot - allow for negative values if baseline subtraction is active
            if self.baseline_subtract_enabled and self.baseline_data is not None:
                # Dynamic range when baseline subtraction is active
                data_min = np.min(data)
                data_max = np.max(data)
                y_margin = (data_max - data_min) * 0.1
                CCDplot.a.set_ylim(data_min - y_margin, data_max + y_margin)
            else:
                # Standard range for normal display
                CCDplot.a.set_ylim(-10, 2250)
        else:
            # plot raw data
            data = config.rxData16.copy()
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
            
            # Apply baseline subtraction if enabled
            if self.baseline_subtract_enabled and self.baseline_data is not None:
                try:
                    # Ensure baseline data has same length as current data
                    if len(self.baseline_data) == len(data):
                        data = data.astype(float) - self.baseline_data.astype(float)
                except Exception as e:
                    print(f"Baseline subtraction error: {e}")

            # Plot raw data directly
            CCDplot.a.plot(x_values, data, alpha=alpha, color=self.main_plot_color)
            CCDplot.a.set_ylabel("ADCcount")
            CCDplot.a.set_xlabel(x_label)
            # Set Y-axis range for raw data plot - allow for negative values if baseline subtraction is active
            if self.baseline_subtract_enabled and self.baseline_data is not None:
                # Dynamic range when baseline subtraction is active
                data_min = np.min(data)
                data_max = np.max(data)
                y_margin = (data_max - data_min) * 0.1
                CCDplot.a.set_ylim(data_min - y_margin, data_max + y_margin)
            else:
                # Standard range for normal display
                CCDplot.a.set_ylim(-10, 4095)

        # Update spectrum background
        self.CCDplot.set_show_colors(self.show_colors.get())

        # If regression toggle is active, compute and plot interpolated curve
        try:
            if getattr(self, "ph_checkbox_var", None) and self.ph_checkbox_var.get() == 1:
                # Use the same data that was plotted (data variable)
                n = data.size
                pixels = np.arange(n)
                intensities = data.astype(float)

                # smoothing parameter from slider (10->no smoothing, 1000->max smoothing)
                try:
                    sval = float(self.ph_scale.get())
                except Exception:
                    sval = 100.0
                # Convert slider value to smoothing factor (10->0, 1000->49.5)
                smooth = max(0.0, (sval - 10.0) / 20.0)

                interp_fn, interp_kind = plotgraph.make_interpolator(pixels, intensities, method="spline", smooth=smooth)
                xs_pix = np.linspace(pixels.min(), pixels.max(), 2000)
                try:
                    ys_interp = interp_fn(xs_pix)
                    ys_interp = np.asarray(ys_interp, dtype=float)
                except Exception:
                    ys_interp = np.interp(xs_pix, pixels, intensities)

                # Map pixel x-coordinates to plot x-coordinates (pixels or calibrated wavelengths)
                if config.spectroscopy_mode and hasattr(default_calibration, "apply") and callable(default_calibration.apply):
                    xs_plot = default_calibration.apply(xs_pix.astype(int))
                else:
                    xs_plot = xs_pix

                # Plot interpolated curve as a distinct coloured line
                CCDplot.a.plot(xs_plot, ys_interp, color=self.regression_color, lw=0.9, alpha=0.9, label="interpolated")
        except Exception:
            # don't let regression failures break the plotting
            pass

        # Plot comparison data if available
        if self.comparison_data is not None:
            try:
                # Assume comparison data is in the same format as main data
                # If it's a 2D array with x and y columns, use both
                if self.comparison_data.ndim == 2 and self.comparison_data.shape[1] >= 2:
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
                if config.spectroscopy_mode and hasattr(default_calibration, "apply") and callable(default_calibration.apply):
                    # If compare_x is already wavelengths, use as-is; otherwise convert from pixels
                    if compare_x.max() < 4000:  # Likely pixel numbers
                        compare_x = default_calibration.apply(compare_x.astype(int))
                
                CCDplot.a.plot(compare_x, compare_y, color=self.compare_color, lw=1.0, alpha=0.8)
            except Exception as e:
                print(f"Error plotting comparison data: {e}")

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
        self.lcontinuous.grid(column=0, row=continuous_row, sticky="e")
        self.roneshot = ttk.Radiobutton(
            self,
            text="One shot",
            variable=self.CONTvar,
            value=0,
            command=lambda CONTvar=self.CONTvar: self.modeset(CONTvar),
        )
        self.roneshot.grid(column=1, row=continuous_row, sticky="w", padx=5)
        self.rcontinuous = ttk.Radiobutton(
            self,
            text="Continuous",
            variable=self.CONTvar,
            value=1,
            command=lambda CONTvar=self.CONTvar: self.modeset(CONTvar),
        )
        self.rcontinuous.grid(column=1, row=continuous_row + 1, sticky="w", padx=5)
        # set initial state
        self.CONTvar.set(config.AVGn[0])

    def avgfields(self, avg_row):
        # average - variables, widgets and traces associated with the average slider
        # widgets
        self.lavg = ttk.Label(self, text="Averages:")
        self.lavg.grid(column=0, row=avg_row, sticky="e")
        self.AVGscale = ttk.Scale(
            self,
            from_=1,
            to=255,
            orient=tk.HORIZONTAL,
            length=200,
            command=self.AVGcallback,
        )
        self.AVGscale.grid(column=1, row=avg_row, padx=5, pady=5, sticky="w")
        self.AVGlabel = ttk.Label(self)
        self.AVGlabel.grid(column=2, row=avg_row, padx=5, pady=5, sticky="w")
        self.AVGscale.set(config.AVGn[1])
        self.AVGlabel.config(text=str(config.AVGn[1]))

    def collectfields(self, collect_row, SerQueue, progress_var):
        # collect and stop buttons
        self.buttonframe = ttk.Frame(self)
        self.buttonframe.grid(row=collect_row, columnspan=2, padx=(35, 0))
        self.bcollect = ttk.Button(
            self.buttonframe,
            text="Collect",
            width=15,
            style="Accent.TButton",
            command=lambda panel=self, SerQueue=SerQueue, progress_var=progress_var: CCDserial.rxtx(
                panel, SerQueue, progress_var
            ),
        )
        self.bcollect.pack(side=tk.LEFT, padx=5, anchor="w")
        self.bstop = ttk.Button(
            self.buttonframe,
            text="Stop",
            width=15,
            command=lambda SerQueue=SerQueue: CCDserial.rxtxcancel(SerQueue),
            state=tk.DISABLED,
        )
        self.bstop.pack(side=tk.RIGHT, padx=5, pady=5, anchor="e")
        
        # Baseline buttons
        self.baseline_frame = ttk.Frame(self)
        self.baseline_frame.grid(row=collect_row + 1, columnspan=2, padx=(35, 0), pady=(5, 0))
        
        self.save_baseline_btn = ttk.Button(
            self.baseline_frame,
            text="Save Baseline",
            width=15,
            command=self._save_baseline
        )
        self.save_baseline_btn.pack(side=tk.LEFT, padx=5, anchor="w")
        
        self.subtract_baseline_btn = ttk.Button(
            self.baseline_frame,
            text="Subtract Baseline",
            width=15,
            command=lambda: self._toggle_baseline_subtract(self.CCDplot),
            state="disabled"
        )
        self.subtract_baseline_btn.pack(side=tk.RIGHT, padx=5, anchor="e")
        
        # progressbar
        self.progress = ttk.Progressbar(
            self, variable=progress_var, maximum=10, length=200,
        )
        self.progress.grid(row=collect_row + 3, columnspan=2, sticky="EW", padx=(45, 5))

    def plotmodefields(self, plotmode_row, CCDplot):
        # plot mode - variables, widgets and traces associated with the plot mode
        # variables
        self.invert = tk.IntVar()
        self.balanced = tk.IntVar()
        self.show_colors = tk.IntVar()
        # plot mode - variables, widgets and traces associated with the plot mode
        # variables
        self.invert = tk.IntVar()
        self.balanced = tk.IntVar()
        self.show_colors = tk.IntVar()

        # widgets
        self.lplot = ttk.Label(self, text="Plot mode:")
        self.lplot.grid(column=0, row=plotmode_row, sticky="e")
        self.cinvert = ttk.Checkbutton(
            self, text="Invert data", variable=self.invert, onvalue=1, offvalue=0
        )
        self.cinvert.grid(column=1, row=plotmode_row, sticky="w", padx=5)
        self.cbalance = ttk.Checkbutton(
            self,
            text="Balance even/odd pixels",
            variable=self.balanced,
            onvalue=1,
            offvalue=0,
            state=tk.DISABLED,
        )
        self.cbalance.grid(column=1, row=plotmode_row + 1, sticky="w", padx=5)

        # Mirror left/right: place below the balance checkbox
        self.mirror = tk.IntVar()
        self.cmirror = ttk.Checkbutton(
            self,
            text="Mirror data",
            variable=self.mirror,
            onvalue=1,
            offvalue=0,
        )
        self.cmirror.grid(column=1, row=plotmode_row + 2, sticky="w", padx=5)

        # Show colors checkbox
        self.cshowcolors = ttk.Checkbutton(
            self,
            text="Show colours",
            variable=self.show_colors,
            onvalue=1,
            offvalue=0,
            command=self.toggle_spectrum_colors,
        )
        # moved down one row because mirror checkbox was inserted
        self.cshowcolors.grid(column=1, row=plotmode_row + 3, sticky="w", padx=5)
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

    def saveopenfields(self, save_row, CCDplot):
        # setup save/open buttons
        self.fileframe = ttk.Frame(self)
        self.fileframe.grid(row=save_row, columnspan=2, padx=(40, 0))
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

        self.bopen.pack(side=tk.LEFT, padx=(5, 0), pady=5)
        self.bsave.pack(side=tk.LEFT, padx=(5, 0), pady=5)
        self.bcalib.pack(
            side=tk.LEFT, padx=(5, 0), pady=5
        )  # Add some padding to separate from save button

        # Now overlay the icon image on top of the buttons
        try:
            from PIL import Image, ImageTk
            import os

            # Prefer a small palette icon if present, fallback to astrolens
            base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
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

        # Add a little vertical spacing before the placeholder controls
        self.grid_rowconfigure(save_row + 1, minsize=12)

        # Placeholder controls: a checkbox and a slider (styled like Averages)
        # Placed below the save/open/calibration buttons
        self.ph_checkbox_var = tk.IntVar(value=0)
        self.ph_check = ttk.Checkbutton(
            self,
            text="Toggle regression",
            variable=self.ph_checkbox_var,
            onvalue=1,
            offvalue=0,
        )
        self.ph_check.grid(column=1, row=save_row + 2, sticky="w", padx=5)
        # Trace the checkbox so we can enable/disable the slider dynamically
        # Also trigger a plot update so the regression overlay appears immediately
        self.ph_checkbox_var.trace_add(
            "write",
            lambda *args, CCDplot=CCDplot: (self._ph_check_changed(), self.updateplot(CCDplot)),
        )

        # Placeholder slider similar to Averages
        self.lphslider = ttk.Label(self, text="Strength")
        self.lphslider.grid(column=0, row=save_row + 3, sticky="e")
        self.ph_scale = ttk.Scale(
            self,
            from_=10,
            to=1000,
            orient=tk.HORIZONTAL,
            length=200,
            command=self._phslider_callback,
        )
        self.ph_scale.grid(column=1, row=save_row + 3, padx=5, pady=5, sticky="w")
        # Update plot only when mouse is released to avoid lag during dragging
        self.ph_scale.bind("<ButtonRelease-1>", lambda e, CCDplot=CCDplot: self._on_regression_release(CCDplot))
        # Use a tk.Label so we can change the foreground color when disabled
        self.ph_label = tk.Label(self, text="0", fg="#ffffff")
        self.ph_label.grid(column=2, row=save_row + 3, padx=5, pady=5, sticky="w")

        # Set initial enabled/disabled state based on the checkbox
        self._ph_check_changed()

        # Opacity slider for the main plot line (0..100 -> 0.0..1.0)
        self.lopacity = ttk.Label(self, text="Raw opacity")
        self.lopacity.grid(column=0, row=save_row + 4, sticky="e")
        self.opacity_scale = ttk.Scale(
            self,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            length=200,
            command=self._opacity_callback,
        )
        self.opacity_scale.grid(column=1, row=save_row + 4, padx=5, pady=5, sticky="w")
        self.opacity_label = ttk.Label(self, text="1.00")
        self.opacity_label.grid(column=2, row=save_row + 4, padx=5, pady=5, sticky="w")
        self.opacity_scale.set(100)

        # Element matching checkbox
        self.element_match_var = tk.IntVar(value=0)
        self.element_match_check = ttk.Checkbutton(
            self,
            text="Match emission lines",
            variable=self.element_match_var,
            onvalue=1,
            offvalue=0,
        )
        self.element_match_check.grid(column=1, row=save_row + 5, sticky="w", padx=5)
        self.element_match_var.trace_add(
            "write",
            lambda *args: self.CCDplot.update_marker_colors(bool(self.element_match_var.get())),
        )

        # Tolerance settings for emission line matching
        tolerance_frame = ttk.Frame(self)
        tolerance_frame.grid(column=0, row=save_row + 6, padx=(45, 5), pady=(10, 5), columnspan=3, sticky="w")
        
        # Green tolerance (exact match)
        ttk.Label(tolerance_frame, text="Green:").grid(row=0, column=0, padx=(0, 2), sticky="e")
        self.green_tolerance_var = tk.DoubleVar(value=config.green_tolerance_nm)
        green_entry = ttk.Entry(tolerance_frame, textvariable=self.green_tolerance_var, width=6)
        green_entry.grid(row=0, column=1, padx=2)
        ttk.Label(tolerance_frame, text="nm").grid(row=0, column=2, padx=(0, 8), sticky="w")
        
        # Yellow tolerance (close match)
        ttk.Label(tolerance_frame, text="Yellow:").grid(row=0, column=3, padx=2, sticky="e")
        self.yellow_tolerance_var = tk.DoubleVar(value=config.yellow_tolerance_nm)
        yellow_entry = ttk.Entry(tolerance_frame, textvariable=self.yellow_tolerance_var, width=6)
        yellow_entry.grid(row=0, column=4, padx=2)
        ttk.Label(tolerance_frame, text="nm").grid(row=0, column=5, padx=(0, 8), sticky="w")
        
        # Apply button in same row
        ttk.Button(
            tolerance_frame,
            text="Apply",
            command=self.apply_tolerance_settings,
            style="Accent.TButton"
        ).grid(row=0, column=6, padx=5)
        
        # Center the tolerance frame
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

    def open_calibration(self):
        """Open calibration window with proper callback reference"""
        default_calibration.open_calibration_window(
            self.master, on_apply_callback=self.CCDplot.replot_current_spectrum
        )
    
    def load_com_settings(self):
        """Load COM settings from file"""
        try:
            if os.path.exists(COM_SETTINGS_FILE):
                with open(COM_SETTINGS_FILE, "r") as f:
                    settings = json.load(f)
                    config.port = settings.get("port", config.port)
                    # Load firmware type if saved
                    if "firmware" in settings:
                        config.saved_firmware = settings.get("firmware", "STM32F40x")
        except Exception as e:
            print(f"Could not load COM settings: {e}")
    
    def save_com_settings(self):
        """Save COM settings to file"""
        try:
            settings = {
                "port": self.device_address.get(),
                "firmware": self.firmware_type.get()
            }
            with open(COM_SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=4)
            # Update config
            config.port = self.device_address.get()
            return True
        except Exception as e:
            print(f"Could not save COM settings: {e}")
            return False
    
    def add_com_save_button(self, parent_frame):
        """Add save icon button next to COM port entry"""
        # Create button matching the style of other save buttons
        self.b_save_com = ttk.Button(
            parent_frame,
            text="",
            style="Accent.TButton",
            width=3,
            command=self.save_com_settings
        )
        self.b_save_com.pack(side=tk.LEFT, padx=(3, 0))
        
        # Add icon overlay to the button
        try:
            from PIL import Image, ImageTk
            import os
            
            # Get the path to save.png
            base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
            save_icon_path = os.path.join(base_dir, "save.png")
            
            if os.path.exists(save_icon_path):
                save_icon_image = Image.open(save_icon_path).convert("RGBA")
                
                # Make the icon solid black while preserving transparency
                try:
                    save_alpha = save_icon_image.getchannel("A")
                except Exception:
                    save_alpha = save_icon_image.convert("L")
                save_black_img = Image.new("RGBA", save_icon_image.size, (0, 0, 0, 255))
                save_icon_solid = Image.new("RGBA", save_icon_image.size, (0, 0, 0, 0))
                save_icon_solid.paste(save_black_img, (0, 0), mask=save_alpha)
                
                # Resize icon to reasonable size
                target_size = (16, 16)
                try:
                    resample = Image.Resampling.LANCZOS
                except Exception:
                    resample = Image.LANCZOS
                save_icon_resized = save_icon_solid.resize(target_size, resample)
                icon_photo_com = ImageTk.PhotoImage(save_icon_resized)
                
                # Place label with icon on top of the button
                self.icon_overlay_com = tk.Label(
                    self.b_save_com,
                    image=icon_photo_com,
                    bg="#ffc200",
                    bd=0,
                    cursor="hand2",
                )
                self.icon_overlay_com.image = icon_photo_com
                self.icon_overlay_com.place(relx=0.5, rely=0.5, anchor="center")
                self.icon_overlay_com.bind("<Button-1>", lambda e: self.save_com_settings())
        except Exception as e:
            print(f"Could not create COM save icon: {e}")

    def open_color_picker(self):
        """Open color picker window for plot customization"""
        # Check if color picker window already exists and is open
        if hasattr(self, 'color_window') and self.color_window and self.color_window.winfo_exists():
            self.color_window.lift()  # Bring existing window to front
            return
            
        # Create a new top-level window
        self.color_window = tk.Toplevel(self.master)
        self.color_window.title("Plot Colour Settings")
        self.color_window.resizable(False, False)
        
        # Set window size and center it on screen (adjusted for compare data and emission lines sections)
        window_width = 450
        window_height = 620
        screen_width = self.color_window.winfo_screenwidth()
        screen_height = self.color_window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.color_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Clean up reference when window is closed
        self.color_window.protocol("WM_DELETE_WINDOW", lambda: self.close_color_window())
        
        # Main plot color section
        ttk.Label(self.color_window, text="Main Plot Colour:", font=("Avenir", 10, "bold")).pack(pady=(20, 5))
        
        main_color_frame = ttk.Frame(self.color_window)
        main_color_frame.pack(pady=5)
        
        # Color preview for main plot
        self.main_color_preview = tk.Canvas(main_color_frame, width=40, height=40, bg=self.main_plot_color, relief="solid", borderwidth=1)
        self.main_color_preview.pack(side=tk.LEFT, padx=(10, 5))
        
        ttk.Button(
            main_color_frame,
            text="Choose Colour",
            style="Accent.TButton",
            command=lambda: self.choose_plot_color("main", self.color_window)
        ).pack(side=tk.LEFT, padx=5)
        
        # Regression plot color section
        ttk.Label(self.color_window, text="Regression Line Colour:", font=("Avenir", 10, "bold")).pack(pady=(20, 5))
        
        regression_color_frame = ttk.Frame(self.color_window)
        regression_color_frame.pack(pady=5)
        
        # Color preview for regression
        self.regression_color_preview = tk.Canvas(regression_color_frame, width=40, height=40, bg=self.regression_color, relief="solid", borderwidth=1)
        self.regression_color_preview.pack(side=tk.LEFT, padx=(10, 5))
        
        ttk.Button(
            regression_color_frame,
            text="Choose Colour",
            style="Accent.TButton",
            command=lambda: self.choose_plot_color("regression", self.color_window)
        ).pack(side=tk.LEFT, padx=5)
        
        # Emission Lines color section
        ttk.Label(self.color_window, text="Marking lines Colour:", font=("Avenir", 10, "bold")).pack(pady=(5, 5))
        
        emission_color_frame = ttk.Frame(self.color_window)
        emission_color_frame.pack(pady=5)
        
        # Color preview for emission lines
        self.emission_color_preview = tk.Canvas(
            emission_color_frame,
            width=40,
            height=40,
            bg=self.emission_line_color,
            relief="solid",
            borderwidth=1,
        )
        self.emission_color_preview.pack(side=tk.LEFT, padx=(10, 5))

        self.emission_color_button = ttk.Button(
            emission_color_frame,
            text="Choose Colour",
            style="Accent.TButton",
            command=lambda: self.choose_plot_color("emission", self.color_window),
        )
        self.emission_color_button.pack(side=tk.LEFT, padx=5)

        self.update_emission_color_controls()
        
        # Separator
        ttk.Separator(self.color_window, orient="horizontal").pack(fill="x", pady=15)
        
        # Compare data section
        ttk.Label(self.color_window, text="Compare Data:", font=("Avenir", 10, "bold")).pack(pady=(5, 5))
        
        compare_frame = ttk.Frame(self.color_window)
        compare_frame.pack(pady=5)
        
        # Compare data button
        ttk.Button(
            compare_frame,
            text="Load Data File",
            style="Accent.TButton",
            command=self.load_comparison_data
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
            command=lambda: self.close_color_window()
        ).pack(pady=15)

    def apply_tolerance_settings(self):
        """Apply the tolerance settings and refresh the plot"""
        try:
            green_val = self.green_tolerance_var.get()
            yellow_val = self.yellow_tolerance_var.get()
            
            # Validate inputs
            if green_val <= 0 or yellow_val <= 0:
                return
            
            if green_val >= yellow_val:
                # Show warning that green should be less than yellow
                return
            
            # Update config values
            config.green_tolerance_nm = green_val
            config.yellow_tolerance_nm = yellow_val
            
            # Refresh the plot to show updated colors
            if config.spectroscopy_mode:
                self.CCDplot.update_marker_colors(True)
        except ValueError:
            pass  # Invalid number, ignore

    def update_emission_color_controls(self):
        """Enable or disable emission line color controls based on current mode."""
        button = getattr(self, "emission_color_button", None)
        if button:
            try:
                if config.spectroscopy_mode:
                    button.state(["disabled"])
                else:
                    button.state(["!disabled"])
            except Exception:
                try:
                    button.configure(
                        state=tk.DISABLED if config.spectroscopy_mode else tk.NORMAL
                    )
                except Exception:
                    pass

    def load_comparison_data(self):
        """Load a .dat file for comparison"""
        from tkinter import filedialog
        import os
        
        filename = filedialog.askopenfilename(
            title="Select comparison data file",
            filetypes=[("Data files", "*.dat"), ("All files", "*.*")]
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
        if not hasattr(self, 'color_window') or not self.color_window or not self.color_window.winfo_exists():
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
                font=("Avenir", 9)
            )
            filename_label.pack(side=tk.LEFT, padx=5)
            
            remove_btn = ttk.Button(
                self.compare_info_frame,
                text="✕",
                width=3,
                command=self.remove_comparison_data
            )
            remove_btn.pack(side=tk.LEFT, padx=2)
            
            # Show comparison color picker
            self.compare_color_section.pack(pady=5)
            
            ttk.Label(
                self.compare_color_section,
                text="Comparison Data Colour:",
                font=("Avenir", 10, "bold")
            ).pack(pady=(10, 5))
            
            compare_color_frame = ttk.Frame(self.compare_color_section)
            compare_color_frame.pack(pady=5)
            
            # Color preview for comparison
            self.compare_color_preview = tk.Canvas(
                compare_color_frame,
                width=40,
                height=40,
                bg=self.compare_color,
                relief="solid",
                borderwidth=1
            )
            self.compare_color_preview.pack(side=tk.LEFT, padx=(10, 5))
            
            ttk.Button(
                compare_color_frame,
                text="Choose Colour",
                style="Accent.TButton",
                command=lambda: self.choose_plot_color("compare", self.color_window)
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
        if plot_type == "emission" and config.spectroscopy_mode:
            try:
                messagebox.showinfo(
                    "Unavailable",
                    "Marking line colour is only adjustable in Regular mode.",
                    parent=getattr(self, 'color_window', None),
                )
            except Exception:
                pass
            return

        if plot_type == "main":
            current_color = self.main_plot_color
        elif plot_type == "regression":
            current_color = self.regression_color
        elif plot_type == "emission":
            current_color = self.emission_line_color
        else:  # compare
            current_color = self.compare_color

        color = colorchooser.askcolor(color=current_color, title=f"Choose {plot_type} color")

        if color[1]:  # If user didn't cancel
            hex_color = color[1]

            if plot_type == "main":
                self.main_plot_color = hex_color
                self.main_color_preview.config(bg=self.main_plot_color)
                self.updateplot(self.CCDplot)
            elif plot_type == "regression":
                self.regression_color = hex_color
                self.regression_color_preview.config(bg=self.regression_color)
                self.updateplot(self.CCDplot)
            elif plot_type == "compare":
                self.compare_color = hex_color
                self.compare_color_preview.config(bg=self.compare_color)
                self.updateplot(self.CCDplot)
            else:  # emission in regular mode
                self.emission_line_color = hex_color
                if self.emission_color_preview:
                    self.emission_color_preview.config(bg=self.emission_line_color)
                # Update the emission line color in CCDplot and recolor existing markers
                self.CCDplot.emission_line_color = hex_color
                self.CCDplot.update_marker_colors(self.CCDplot.element_matching_enabled)
                self.CCDplot.canvas.draw()

            # Close the window after color selection
            self.close_color_window()

    def close_color_window(self):
        """Close the color picker window and clean up reference"""
        if hasattr(self, 'color_window') and self.color_window and self.color_window.winfo_exists():
            self.color_window.destroy()
        self.color_window = None
        self.emission_color_button = None
        self.emission_color_preview = None

    def zoom_mode(self):
        """Activate zoom mode on the plot"""
        if hasattr(self.CCDplot, 'navigation_toolbar'):
            self.CCDplot.navigation_toolbar.zoom()

    def save_figure(self):
        """Open save dialog to save the figure"""
        if hasattr(self.CCDplot, 'navigation_toolbar'):
            self.CCDplot.navigation_toolbar.save_figure()

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

    def _phslider_callback(self, val):
        """Internal callback for the regression slider to update the label."""
        try:
            v = float(val)
        except Exception:
            v = 10.0
        # Map slider (10..1000) to smoothing factor (0.0001..0.01)
        smooth = v / 100000.0
        # Show smoothing value with 5 decimal precision to see 0.00001 increments
        try:
            self.ph_label.config(text=f"{smooth:.5f}")
        except Exception:
            # fallback to display
            self.ph_label.config(text=f"{v:.0f}")
    
    def _on_regression_release(self, CCDplot):
        """Update plot when regression slider is released."""
        if getattr(self, "ph_checkbox_var", None) and self.ph_checkbox_var.get() == 1:
            try:
                self.updateplot(CCDplot)
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
    
    def _save_baseline(self):
        """Save the current data as baseline for subtraction."""
        try:
            if config.datainvert == 1:
                self.baseline_data = config.pltData16.copy().astype(float)
            else:
                self.baseline_data = config.rxData16.copy().astype(float)
            
            # Apply mirroring if enabled (to match what would be plotted)
            if getattr(config, "datamirror", 0) == 1:
                self.baseline_data = self.baseline_data[::-1]
            
            # Enable the subtract baseline button
            self.subtract_baseline_btn.config(state="normal")
            print(f"Baseline saved successfully: min={np.min(self.baseline_data):.2f}, max={np.max(self.baseline_data):.2f}, mean={np.mean(self.baseline_data):.2f}")
        except Exception as e:
            print(f"Error saving baseline: {e}")
            messagebox.showerror("Baseline Error", f"Failed to save baseline: {e}")
    
    def _toggle_baseline_subtract(self, CCDplot):
        """Toggle baseline subtraction on/off."""
        if self.baseline_data is None:
            messagebox.showwarning("No Baseline", "Please save a baseline first.")
            return
        
        # Toggle the state
        self.baseline_subtract_enabled = not self.baseline_subtract_enabled
        
        # Update button text to reflect state
        if self.baseline_subtract_enabled:
            self.subtract_baseline_btn.config(text="Remove Baseline")
        else:
            self.subtract_baseline_btn.config(text="Subtract Baseline")
        
        # Update the plot
        try:
            self.updateplot(CCDplot)
        except Exception as e:
            print(f"Error updating plot with baseline: {e}")

    def callback(self):
        self.bopen.config(state=tk.DISABLED)
        return ()

    def aboutbutton(self, about_row):
        # Create a frame to hold icon buttons
        button_frame = ttk.Frame(self)
        button_frame.grid(row=about_row, columnspan=3, padx=(0, 30))
        
        # Create three icon buttons
        self.b_icon = ttk.Button(
            button_frame,
            text="",
            style="Accent.TButton",
            width=3,
            command=self.open_color_picker,
        )
        self.b_icon.pack(side=tk.LEFT, padx=(0, 2))

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
        self.b_save_img.pack(side=tk.LEFT, padx=(2, 5))
        
        # Add icon overlays to the buttons
        try:
            from PIL import Image, ImageTk
            import os

            base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
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

                # Place icon on zoom button (use image_icon.png)
                save_icon_path = os.path.join(base_dir, "image_icon.png")
                if os.path.exists(save_icon_path):
                    save_icon_image = Image.open(save_icon_path).convert("RGBA")
                    # Make black
                    try:
                        save_alpha = save_icon_image.getchannel("A")
                    except Exception:
                        save_alpha = save_icon_image.convert("L")
                    save_black_img = Image.new("RGBA", save_icon_image.size, (0, 0, 0, 255))
                    save_icon_solid = Image.new("RGBA", save_icon_image.size, (0, 0, 0, 0))
                    save_icon_solid.paste(save_black_img, (0, 0), mask=save_alpha)
                    save_icon_resized = save_icon_solid.resize((20, 20), resample)
                    icon_photo_zoom = ImageTk.PhotoImage(save_icon_resized)
                else:
                    icon_photo_zoom = ImageTk.PhotoImage(icon_solid.resize((20, 20), resample))
                
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
                    lens_black_img = Image.new("RGBA", lens_icon_image.size, (0, 0, 0, 255))
                    lens_icon_solid = Image.new("RGBA", lens_icon_image.size, (0, 0, 0, 0))
                    lens_icon_solid.paste(lens_black_img, (0, 0), mask=lens_alpha)
                    lens_icon_resized = lens_icon_solid.resize(target_size, resample)
                    icon_photo_save = ImageTk.PhotoImage(lens_icon_resized)
                else:
                    icon_photo_save = ImageTk.PhotoImage(icon_solid.resize(target_size, resample))
                
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
        self.bhelp.pack(side=tk.LEFT, padx=(0, 0))

    def open_help_url(self):
        """Open the help URL in the default browser"""
        try:
            webbrowser.open("https://www.astrolens.net/pyspec-help")
        except Exception as e:
            print(f"Failed to open browser: {e}")