import tkinter as tk
from tkinter import ttk
import numpy as np
import json
import os
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Calibration data file
CALIBRATION_FILE = "calibration_params.json"

# Default calibration points (your original 4-point polynomial)
default_calibration = {
    "points": [
        {"pixel": 0, "wavelength": 350.0},
        {"pixel": 1231, "wavelength": 532.0},
        {"pixel": 2462, "wavelength": 700.0},
        {"pixel": 3693, "wavelength": 800.0},
    ]
}

# Global calibration data
calibration_data = default_calibration.copy()


def load_calibration():
    """Load calibration from file"""
    global calibration_data
    try:
        if os.path.exists(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, "r") as f:
                calibration_data = json.load(f)
                # Ensure we have exactly 4 points
                if len(calibration_data.get("points", [])) != 4:
                    calibration_data = default_calibration.copy()
                    save_calibration()
    except:
        calibration_data = default_calibration.copy()


def save_calibration():
    """Save calibration to file"""
    try:
        with open(CALIBRATION_FILE, "w") as f:
            json.dump(calibration_data, f, indent=4)
        return True
    except:
        return False


def apply(pixels):
    """Apply 4-point polynomial calibration (your original function)"""
    points = calibration_data["points"]

    # Extract pixel and wavelength values
    pixel_vals = [point["pixel"] for point in points]
    wavelength_vals = [point["wavelength"] for point in points]

    # Fit 3rd degree polynomial (4 points = 3rd degree)
    coefficients = np.polyfit(pixel_vals, wavelength_vals, 3)
    polynomial = np.poly1d(coefficients)

    return polynomial(pixels)


def calculate_calibration_curve(points):
    """Calculate the calibration curve for preview"""
    pixel_vals = [point["pixel"] for point in points]
    wavelength_vals = [point["wavelength"] for point in points]

    coefficients = np.polyfit(pixel_vals, wavelength_vals, 3)
    polynomial = np.poly1d(coefficients)

    # Generate smooth curve for plotting
    x_plot = np.linspace(0, 3693, 100)
    y_plot = polynomial(x_plot)

    return x_plot, y_plot, pixel_vals, wavelength_vals


class CalibrationWindow:
    def __init__(self, parent, on_apply_callback=None):
        self.parent = parent
        self.on_apply_callback = on_apply_callback
        self.window = tk.Toplevel(parent)
        self.window.title("CCD Calibration")
        self.window.geometry("600x600")

        self.point_vars = []
        self.create_widgets()
        self.update_preview()

    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Calibration points frame
        points_frame = ttk.LabelFrame(
            main_frame, text="Calibration Points (4-point polynomial)", padding="10"
        )
        points_frame.pack(fill=tk.X, pady=5)

        # Create input fields for 4 points
        labels = ["Pixel:", "Wavelength (nm):"]
        for i, point in enumerate(calibration_data["points"]):
            point_frame = ttk.Frame(points_frame)
            point_frame.pack(fill=tk.X, pady=2)

            ttk.Label(point_frame, text=labels[0]).pack(side=tk.LEFT)
            pixel_var = tk.StringVar(value=str(point["pixel"]))
            pixel_entry = ttk.Entry(point_frame, textvariable=pixel_var, width=10)
            pixel_entry.pack(side=tk.LEFT, padx=5)

            ttk.Label(point_frame, text=labels[1]).pack(side=tk.LEFT)
            wavelength_var = tk.StringVar(value=str(point["wavelength"]))
            wavelength_entry = ttk.Entry(
                point_frame, textvariable=wavelength_var, width=10
            )
            wavelength_entry.pack(side=tk.LEFT, padx=5)

            # Bind updates to preview
            pixel_var.trace_add("write", lambda *args: self.update_preview())
            wavelength_var.trace_add("write", lambda *args: self.update_preview())

            self.point_vars.append({"pixel": pixel_var, "wavelength": wavelength_var})

        # Preview graph frame
        preview_frame = ttk.LabelFrame(
            main_frame, text="Calibration Curve Preview", padding="10"
        )
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create matplotlib figure
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, preview_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Status message at the bottom
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_label = ttk.Label(
            main_frame, textvariable=self.status_var, foreground="green"
        )
        self.status_label.pack(pady=5)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Apply", command=self.apply_calibration).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        ttk.Button(button_frame, text="Save", command=self.save_calibration).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        ttk.Button(
            button_frame, text="Reset to Defaults", command=self.reset_defaults
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Close button (separate from Apply)
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(
            side=tk.RIGHT
        )

    def update_status(self, message, is_error=False):
        """Update status message at the bottom"""
        self.status_var.set(message)
        if is_error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="green")

    def update_preview(self):
        """Update the preview graph"""
        points = self.get_points_from_ui()

        try:
            x_plot, y_plot, pixel_vals, wavelength_vals = calculate_calibration_curve(
                points
            )

            self.ax.clear()
            self.ax.plot(x_plot, y_plot, "b-", label="Calibration curve")
            self.ax.plot(
                pixel_vals,
                wavelength_vals,
                "ro",
                markersize=8,
                label="Calibration points",
            )
            self.ax.set_xlabel("Pixel")
            self.ax.set_ylabel("Wavelength (nm)")
            self.ax.grid(True)
            self.ax.legend()
            self.fig.tight_layout()
            self.canvas.draw()
            self.update_status("Preview updated")
        except Exception as e:
            # If there's an error in calculation, show empty plot
            self.ax.clear()
            self.ax.text(
                0.5,
                0.5,
                "Invalid calibration points",
                horizontalalignment="center",
                verticalalignment="center",
                transform=self.ax.transAxes,
            )
            self.ax.set_xlabel("Pixel")
            self.ax.set_ylabel("Wavelength (nm)")
            self.canvas.draw()
            self.update_status(f"Invalid points: Check input values", is_error=True)
            print(e)

    def get_points_from_ui(self):
        """Get calibration points from UI fields"""
        points = []
        for point_vars in self.point_vars:
            try:
                pixel = int(point_vars["pixel"].get())
                wavelength = float(point_vars["wavelength"].get())
                points.append({"pixel": pixel, "wavelength": wavelength})
            except (ValueError, TypeError):
                # If invalid, skip this point
                continue

        # Ensure we have exactly 4 points, otherwise use defaults
        if len(points) != 4:
            points = default_calibration["points"]

        return points

    def apply_calibration(self):
        """Apply calibration and auto-save"""
        global calibration_data
        try:
            points = self.get_points_from_ui()
            # Validate points
            if len(points) != 4:
                self.update_status(
                    "Error: Need exactly 4 valid calibration points", is_error=True
                )
                return

            calibration_data["points"] = points
            if save_calibration():
                self.update_status("Calibration applied and saved successfully!")
            else:
                self.update_status(
                    "Calibration applied but could not save to file", is_error=True
                )

            if self.on_apply_callback:
                self.on_apply_callback()
        except Exception as e:
            self.update_status(f"Error applying calibration: {e}", is_error=True)

    def save_calibration(self):
        """Save calibration without applying"""
        global calibration_data
        try:
            points = self.get_points_from_ui()
            # Validate points
            if len(points) != 4:
                self.update_status(
                    "Error: Need exactly 4 valid calibration points", is_error=True
                )
                return

            calibration_data["points"] = points
            if save_calibration():
                self.update_status("Calibration saved successfully!")
            else:
                self.update_status("Could not save calibration file", is_error=True)
        except Exception as e:
            self.update_status(f"Error saving calibration: {e}", is_error=True)

    def reset_defaults(self):
        """Reset to default calibration points"""
        for i, point_vars in enumerate(self.point_vars):
            point_vars["pixel"].set(str(default_calibration["points"][i]["pixel"]))
            point_vars["wavelength"].set(
                str(default_calibration["points"][i]["wavelength"])
            )
        self.update_preview()
        self.update_status("Reset to default calibration points")


def open_calibration_window(parent, on_apply_callback=None):
    """Open calibration window"""
    load_calibration()  # Load saved calibration
    return CalibrationWindow(parent, on_apply_callback)


# Load calibration when module starts
load_calibration()
