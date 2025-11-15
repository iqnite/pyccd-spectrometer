import matplotlib
import numpy as np
import tkinter as tk
from tkinter import ttk

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
from matplotlib.figure import Figure
from spectrometer import config, calibration
from spectrometer.spectrum_gradient import update_spectrum_background


class BuildPlot(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        # Configure this frame to expand
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Remove fixed figsize so it can expand
        self.f = Figure(dpi=100, tight_layout=True)
        self.a = self.f.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.f, master=self)
        self.canvas.draw()

        # Use sticky="nsew" to make canvas expand
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        toolbarFrame = ttk.Frame(master=self)
        toolbarFrame.grid(row=1, column=0, sticky="ew")
        
        # Customize toolbar to remove first 3 buttons (Home, Back, Forward)
        NavigationToolbar2Tk.toolitems = [t for t in NavigationToolbar2Tk.toolitems if t[0] not in ('Home', 'Back', 'Forward')]
        
        self.navigation_toolbar = NavigationToolbar2Tk(self.canvas, toolbarFrame)

        # Override toolbar colors to force light mode
        try:
            for child in self.navigation_toolbar.winfo_children():
                if isinstance(child, (tk.Button, tk.Checkbutton)):
                    child.configure(bg="lightgray", activebackground="gray")
                    child.update()
        except Exception as e:
            print(f"Could not set toolbar colors: {e}")

        self.current_data = None  # store last spectrum

        # Variables for panning
        self.pan_start = None
        self.xlim = None
        self.ylim = None

        # Store references for spectrum background updates
        self.spectroscopy_mode = config.spectroscopy_mode
        self.show_colors = False

        # Connect mouse events
        self.connect_mouse_events()

        # Connect axis change event for automatic background updates
        self.a.callbacks.connect("xlim_changed", self.on_axis_change)
        self.a.callbacks.connect("ylim_changed", self.on_axis_change)

    def connect_mouse_events(self):
        """Connect mouse events for zoom and pan"""
        self.canvas.mpl_connect("scroll_event", self.on_mouse_scroll)
        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_motion)

    def on_axis_change(self, event=None):
        """Called automatically when axis limits change"""
        self.update_spectrum_background()
        self.canvas.draw_idle()

    def update_spectrum_background(self):
        """Update spectrum background based on current settings"""
        try:
            # Get current settings
            current_spectroscopy_mode = config.spectroscopy_mode
            current_show_colors = getattr(self, "show_colors", False)

            # Always call the update function to handle axis changes and settings
            update_spectrum_background(
                self.a, current_spectroscopy_mode, current_show_colors
            )
            self.spectroscopy_mode = current_spectroscopy_mode
            self.show_colors = current_show_colors

        except Exception as e:
            print(f"Error updating spectrum background: {e}")

    def on_mouse_scroll(self, event):
        """Zoom with mouse wheel"""
        if event.inaxes != self.a:
            return

        base_scale = 1.1
        xdata = event.xdata
        ydata = event.ydata

        # Get current limits
        xlim = self.a.get_xlim()
        ylim = self.a.get_ylim()

        if event.button == "up":
            # Zoom in
            scale_factor = 1 / base_scale
        elif event.button == "down":
            # Zoom out
            scale_factor = base_scale
        else:
            # No scroll action
            return

        # Calculate new limits
        new_width = (xlim[1] - xlim[0]) * scale_factor
        new_height = (ylim[1] - ylim[0]) * scale_factor

        # Calculate new limits centered on mouse position
        relx = (xlim[1] - xdata) / (xlim[1] - xlim[0])
        rely = (ylim[1] - ydata) / (ylim[1] - ylim[0])

        new_xlim = [xdata - new_width * (1 - relx), xdata + new_width * relx]
        new_ylim = [ydata - new_height * (1 - rely), ydata + new_height * rely]

        # Apply new limits
        self.a.set_xlim(tuple(new_xlim))
        self.a.set_ylim(tuple(new_ylim))
        self.canvas.draw_idle()

    def on_mouse_press(self, event):
        """Start panning on middle mouse button press"""
        if event.inaxes != self.a:
            return

        if event.button == 2:  # Middle mouse button
            self.pan_start = (event.xdata, event.ydata)
            self.xlim = self.a.get_xlim()
            self.ylim = self.a.get_ylim()

    def on_mouse_release(self, event):
        """Stop panning on mouse release"""
        if event.button == 2:  # Middle mouse button
            self.pan_start = None
            self.xlim = None
            self.ylim = None

    def on_mouse_motion(self, event):
        """Pan the graph when middle mouse button is held down"""
        if self.pan_start is None or event.inaxes != self.a:
            return

        dx = event.xdata - self.pan_start[0]
        dy = event.ydata - self.pan_start[1]

        # Calculate new limits
        assert self.xlim is not None and self.ylim is not None
        new_xlim = (self.xlim[0] - dx, self.xlim[1] - dx)
        new_ylim = (self.ylim[0] - dy, self.ylim[1] - dy)

        # Apply new limits
        self.a.set_xlim(new_xlim)
        self.a.set_ylim(new_ylim)
        self.canvas.draw_idle()

    def reset_view(self):
        """Reset the view to original limits"""
        if hasattr(self, "original_xlim") and hasattr(self, "original_ylim"):
            self.a.set_xlim(self.original_xlim)
            self.a.set_ylim(self.original_ylim)
            self.canvas.draw_idle()

    def plot_spectrum(self, ccd_data):
        """Plot spectrum using appropriate x-axis based on mode"""
        self.current_data = ccd_data

        # Choose x-axis based on mode
        if config.spectroscopy_mode:
            x_values = calibration.default_calibration.apply(np.arange(len(ccd_data)))
            x_label = "Wavelength (nm)"
        else:
            x_values = np.arange(len(ccd_data))
            x_label = "Pixel Number"

        self.a.clear()
        self.a.plot(x_values, ccd_data, color="blue")
        self.a.set_xlabel(x_label)
        self.a.set_ylabel("Intensity")
        self.a.grid(True)

        # Store original limits for reset functionality
        self.original_xlim = self.a.get_xlim()
        self.original_ylim = self.a.get_ylim()

        # Update spectrum background
        self.update_spectrum_background()

        self.canvas.draw()

    def replot_current_spectrum(self):
        """Replot last spectrum with current mode settings"""
        if self.current_data is not None:
            self.plot_spectrum(self.current_data)

    def set_show_colors(self, show_colors):
        """Update show_colors setting and refresh background"""
        self.show_colors = show_colors
        self.update_spectrum_background()
        self.canvas.draw_idle()
