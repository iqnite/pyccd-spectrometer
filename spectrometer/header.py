"""
Top panel for the spectrometer GUI
"""

import os
import tkinter as tk
from tkinter import ttk
import numpy as np
from PIL import Image, ImageTk

from spectrometer import CCDplots, config
from spectrometer.calibration import default_calibration


class HeaderPanel(ttk.Frame):
    def __init__(self, master, CCDplot: CCDplots.BuildPlot, SerQueue):
        super().__init__(master)

        # Store CCDplot reference for callbacks
        self.CCDplot = CCDplot

        self.logo_display()
        self.mode_fields()
        self.close_button()

    def close_button(self):
        """Add close button"""
        self.bclose = ttk.Button(
            self,
            text="X",
            style="Accent.TButton",
            command=lambda root=self.master: root.destroy(),
        )
        self.bclose.pack(side=tk.RIGHT, padx=5)

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
