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
        
        # Create secondary x-axis at the top for markers
        self.ax_top = self.a.twiny()
        self.ax_top.set_xlabel('')
        self.ax_top.set_xticks([])  # Start with no ticks
        
        self.canvas = FigureCanvasTkAgg(self.f, master=self)
        self.canvas.draw()

        # Use sticky="nsew" to make canvas expand
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Create a hidden frame for the toolbar (NavigationToolbar2Tk uses pack internally)
        toolbar_container = ttk.Frame(self)
        self.navigation_toolbar = NavigationToolbar2Tk(self.canvas, toolbar_container)
        # Don't grid the toolbar_container at all - keeps it hidden

        self.current_data = None  # store last spectrum

        # Variables for panning
        self.pan_start = None
        self.xlim = None
        self.ylim = None

        # Store references for spectrum background updates
        self.spectroscopy_mode = config.spectroscopy_mode
        self.show_colors = False

        # Storage for user-placed markers
        self.markers = []  # List of (line, text) tuples

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
        # Sync top axis limits with bottom axis
        self.ax_top.set_xlim(self.a.get_xlim())
        self.update_spectrum_background()
        self.update_axis_ticks()
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
        if event.inaxes != self.a and event.inaxes != self.ax_top:
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
        
        # Sync top axis
        self.ax_top.set_xlim(tuple(new_xlim))
        
        self.canvas.draw_idle()

    def on_mouse_press(self, event):
        """Start panning on middle mouse button press, add/remove markers"""
        if event.inaxes != self.a and event.inaxes != self.ax_top:
            return

        if event.button == 1:  # Left mouse button - add marker
            self.add_marker(event.xdata)
        elif event.button == 2:  # Middle mouse button
            self.pan_start = (event.xdata, event.ydata)
            self.xlim = self.a.get_xlim()
            self.ylim = self.a.get_ylim()
        elif event.button == 3:  # Right mouse button - remove marker
            self.remove_marker(event.xdata)

    def on_mouse_release(self, event):
        """Stop panning on mouse release"""
        if event.button == 2:  # Middle mouse button
            self.pan_start = None
            self.xlim = None
            self.ylim = None

    def on_mouse_motion(self, event):
        """Pan the graph when middle mouse button is held down"""
        if self.pan_start is None or (event.inaxes != self.a and event.inaxes != self.ax_top):
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
        
        # Sync top axis
        self.ax_top.set_xlim(new_xlim)
        
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

        # Clear markers when plotting new spectrum
        self.clear_markers()

        self.a.clear()
        
        # Recreate top axis to clear any artifacts
        if hasattr(self, 'ax_top'):
            self.ax_top.remove()
        self.ax_top = self.a.twiny()
        self.ax_top.set_xlabel('')
        self.ax_top.set_xticks([])
        
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

    def add_marker(self, x_pos):
        """Add a vertical marker line at the specified x position"""
        if x_pos is None:
            return
        
        # Get current x-axis limits
        xlim = self.a.get_xlim()
        
        # Validate x_pos is within bounds and not at the origin (likely a bug)
        if x_pos < xlim[0] or x_pos > xlim[1]:
            return
        
        # Ignore clicks very close to zero (likely unintended)
        if abs(x_pos) < (xlim[1] - xlim[0]) * 0.001:
            return

        # Get y-axis limits to draw line from bottom to top
        ylim = self.a.get_ylim()

        # Create vertical line
        line = self.a.axvline(x=x_pos, color="red", linewidth=1, linestyle="-", alpha=0.7)

        # Determine label based on spectroscopy mode (without units)
        if config.spectroscopy_mode:
            label_text = f"{x_pos:.2f}"
        else:
            label_text = f"{int(x_pos)}"

        # Store the marker (line, label, x_pos)
        self.markers.append((line, label_text, x_pos))

        # Update axis ticks to include this marker
        self.update_axis_ticks()

        # Redraw the canvas
        self.canvas.draw_idle()

    def remove_marker(self, x_pos):
        """Remove the marker closest to the specified x position"""
        if x_pos is None or not self.markers:
            return

        # Don't allow deletion when zoom or pan tool is active
        if hasattr(self.navigation_toolbar, 'mode') and self.navigation_toolbar.mode:
            return

        # Find the closest marker
        closest_marker = None
        min_distance = float("inf")

        for marker in self.markers:
            line, label_text, marker_x = marker
            distance = abs(marker_x - x_pos)
            if distance < min_distance:
                min_distance = distance
                closest_marker = marker

        # Remove if within reasonable distance (1% of x-axis range)
        xlim = self.a.get_xlim()
        threshold = abs(xlim[1] - xlim[0]) * 0.01

        if closest_marker and min_distance < threshold:
            line, label_text, marker_x = closest_marker
            line.remove()
            self.markers.remove(closest_marker)
            self.update_axis_ticks()
            self.canvas.draw_idle()

    def update_axis_ticks(self):
        """Update top x-axis ticks to show marker positions"""
        if not self.markers:
            # Clear top axis completely if no markers
            self.ax_top.set_xticks([])
            self.ax_top.set_xticklabels([])
            return

        # Sync the top axis limits with bottom axis
        self.ax_top.set_xlim(self.a.get_xlim())
        
        # Set only marker positions on top axis
        marker_positions = [x_pos for _, _, x_pos in self.markers]
        marker_labels = [label_text for _, label_text, _ in self.markers]
        
        self.ax_top.set_xticks(marker_positions)
        self.ax_top.set_xticklabels(marker_labels)
        
        # Color all marker tick labels red
        for label in self.ax_top.get_xticklabels():
            label.set_color('red')

    def clear_markers(self):
        """Remove all markers"""
        for line, label_text, x_pos in self.markers:
            line.remove()
        self.markers.clear()
        
        # Completely clear top axis
        if hasattr(self, 'ax_top'):
            self.ax_top.cla()
            self.ax_top.set_xlabel('')
            self.ax_top.set_xticks([])
            self.ax_top.set_xticklabels([])
            # Re-sync limits
            self.ax_top.set_xlim(self.a.get_xlim())
        
        self.canvas.draw_idle()
