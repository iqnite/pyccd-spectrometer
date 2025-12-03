"""
Top panel for the spectrometer GUI
"""

import math
import os
import tkinter as tk
from tkinter import ttk
import webbrowser
import numpy as np
from PIL import Image, ImageTk
import serial

from spectrometer import CCDplots, config
from spectrometer.calibration import default_calibration


class HeaderPanel(ttk.Frame):
    def __init__(self, master, CCDplot: CCDplots.BuildPlot, SerQueue):
        super().__init__(master)

        # Store CCDplot reference for callbacks
        self.CCDplot = CCDplot

        self.logo_display()
        self.mode_fields()
        self.devicefields()
        self.CCDparamfields()
        self.right_buttons()

    def right_buttons(self):
        """Add close and help buttons"""
        self.bclose = ttk.Button(
            self,
            text="X",
            style="Accent.TButton",
            command=lambda root=self.master: root.destroy(),
        )
        self.bclose.pack(side=tk.RIGHT, padx=5)

        self.bhelp = ttk.Button(
            self,
            text="Help",
            width=7,
            command=self.open_help_url,
        )
        self.bhelp.pack(side=tk.RIGHT, padx=5)

    def open_help_url(self):
        """Open the help URL in the default browser"""
        try:
            webbrowser.open("https://www.astrolens.net/pyspec-help")
        except Exception as e:
            print(f"Failed to open browser: {e}")

    def logo_display(self):
        """Display the Astrolens logo at the top of the panel"""
        try:
            # Get the path to the PNG file
            logo_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "assets", "astrolens.png"
            )

            if os.path.exists(logo_path):
                logo_image = Image.open(logo_path)

                # Calculate proper aspect ratio resize
                target_width = 100
                aspect_ratio = logo_image.width / logo_image.height
                target_height = int(target_width / aspect_ratio)

                logo_image = logo_image.resize(
                    (target_width, target_height), Image.Resampling.LANCZOS
                )
                logo_photo = ImageTk.PhotoImage(logo_image)

                self.logo_label = ttk.Label(self, image=logo_photo)
                self.logo_label.image = logo_photo  # type: ignore to avoid garbage collection
                self.logo_label.pack(side=tk.LEFT, padx=5)
            else:
                print(f"Logo file not found at {logo_path}")
        except Exception as e:
            print(f"Could not load logo: {e}")

    def mode_fields(self):
        """Add spectroscopy mode toggle"""
        self.operation_mode_frame = ttk.Frame(self)
        self.operation_mode_frame.pack(side=tk.LEFT, padx=5, pady=5)

        self.mode_var = tk.IntVar(value=0)  # 0 = Regular, 1 = Spectroscopy

        self.r_spectroscopy = ttk.Checkbutton(
            self.operation_mode_frame,
            text="Spectroscopy",
            variable=self.mode_var,
            onvalue=1,
            offvalue=0,
            command=self.mode_changed,
            style="Toggle.Switch.TCheckbutton",
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
        self.CCDplot.set_show_colors(self.CCDplot.show_colors.get())
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
        # variables
        self.device_address = tk.StringVar()
        self.device_status = tk.StringVar()
        self.device_statuscolor = tk.StringVar()

        self.port_frame = ttk.LabelFrame(self, text="Port")
        self.port_frame.pack(side=tk.LEFT, padx=5, fill="y")

        # RX port
        self.ldevice = ttk.Label(self.port_frame, text="RX/TX:")
        self.ldevice.grid(row=0, column=0, padx=5)
        self.edevice = ttk.Entry(
            self.port_frame, textvariable=self.device_address, width=7
        )
        self.edevice.grid(row=0, column=1, padx=5)
        self.ldevicestatus = tk.Label(
            self.port_frame, textvariable=self.device_status, fg="#ffffff"
        )
        self.ldevicestatus.grid(row=1, column=1, padx=5)

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
        self.device_status_tx = tk.StringVar(value="Using RX")

        self.ldevice_tx = ttk.Label(self.port_frame, text="TX:")
        self.ldevice_tx.grid(row=0, column=2, padx=5)
        self.edevice_tx = ttk.Entry(
            self.port_frame, textvariable=self.device_address_tx, width=7
        )
        self.edevice_tx.grid(row=0, column=3, padx=5)
        self.ldevicestatus_tx = tk.Label(
            self.port_frame, textvariable=self.device_status_tx, fg="#888888"
        )
        self.ldevicestatus_tx.grid(row=1, column=3, padx=5)
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
        self.lfirmware = ttk.LabelFrame(self, text="Firmware")
        self.lfirmware.pack(side=tk.LEFT, padx=5, fill="y")
        self.firmware_type = tk.StringVar(value="STM32F40x")
        self.firmware_dropdown = ttk.Combobox(
            self.lfirmware,
            textvariable=self.firmware_type,
            values=["STM32F40x", "STM32F103"],
            state="readonly",
            width=10,
        )
        self.firmware_dropdown.pack(side=tk.LEFT, padx=5)
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
                status.set("Found")
                ser.close()
                colr.configure(fg="#ffffff")
            except serial.SerialException:
                status.set("Not found")
                colr.configure(fg="#ffc200")

    def DEVcallback_tx(self, name, index, mode, Device, status, colr):
        tx_port = Device.get().strip()

        # If TX port is empty, use same as RX port
        if not tx_port:
            config.port_tx = None
            status.set("Using RX")
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
                status.set("Found")
                ser.close()
                colr.configure(fg="#ffffff")
            except serial.SerialException:
                status.set("Not found")
                colr.configure(fg="#ffc200")

    def CCDparamfields(self):
        # CCD parameters - variables, widgets and traces associated with setting exposure
        # variables
        self.SH = tk.StringVar()
        self.ICG = tk.StringVar()
        self.tint_status = tk.StringVar()
        self.tint_statuscolor = tk.StringVar()
        self.tint_value = tk.StringVar()  # For exposure time numeric input
        self.tint_unit = tk.StringVar(value="ms")  # Default unit

        # Exposure time input
        self.l_exposure = ttk.LabelFrame(self, text="Exposure Time")
        self.l_exposure.pack(side=tk.LEFT, padx=5, fill="y")
        self.e_tint = ttk.Entry(self.l_exposure, textvariable=self.tint_value, width=6)
        self.e_tint.pack(side=tk.LEFT, padx=5)
        self.unit_dropdown = ttk.Combobox(
            self.l_exposure,
            textvariable=self.tint_unit,
            values=["us", "ms", "s", "min"],
            state="readonly",
            width=2,
        )
        self.unit_dropdown.pack(side=tk.LEFT, padx=5)

        # Original SH/ICG fields
        self.lSH = ttk.LabelFrame(self, text="SH-period")
        self.lSH.pack(side=tk.LEFT, padx=5, fill="y")
        self.eSH = ttk.Entry(self.lSH, textvariable=self.SH, width=6)
        self.eSH.pack(side=tk.LEFT, padx=5)

        self.lICG = ttk.LabelFrame(self, text="ICG-period")
        self.lICG.pack(side=tk.LEFT, padx=5, fill="y")
        self.eICG = ttk.Entry(self.lICG, textvariable=self.ICG, width=7)
        self.eICG.pack(side=tk.LEFT, padx=5)

        # Status labels
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(side=tk.LEFT, padx=5, fill="y")
        self.lccdstatus = tk.Label(self.status_frame, textvariable=self.tint_status)
        self.lccdstatus.pack(side=tk.TOP, pady=5)
        self.ltint = tk.Label(self.status_frame, textvariable=self.tint_statuscolor)
        self.ltint.pack(side=tk.TOP, pady=5)

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
