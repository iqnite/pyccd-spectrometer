import matplotlib
import numpy as np
import tkinter as tk
from tkinter import ttk
import json
import os
import sys

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
        self.ax_top.set_xlabel("")
        self.ax_top.set_xticks([])  # Start with no ticks

        self.canvas = FigureCanvasTkAgg(self.f, master=self)
        self.canvas.draw()

        # Use sticky="nsew" to make canvas expand
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Create a hidden frame for the toolbar (NavigationToolbar2Tk uses pack internally)
        toolbar_container = ttk.Frame(self)
        self.navigation_toolbar = NavigationToolbar2Tk(self.canvas, toolbar_container)
        # Replace the save_figure method to use our spectrum export instead
        self.navigation_toolbar.save_figure = self.save_spectrum_image
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
        self.markers = (
            []
        )  # List of (line, label_text, x_pos, element_text_obj, label_text_obj) tuples
        self.element_matching_enabled = False
        self.emission_line_color = (
            "red"  # Default color for emission lines when not matched
        )

        # Load element emission lines data
        self.emission_lines = self._load_emission_lines()

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

        # Don't allow marker creation/deletion when zoom or pan tool is active
        if hasattr(self.navigation_toolbar, "mode") and self.navigation_toolbar.mode:
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
        if self.pan_start is None or (
            event.inaxes != self.a and event.inaxes != self.ax_top
        ):
            return

        # Get current limits
        cur_xlim = self.a.get_xlim()
        cur_ylim = self.a.get_ylim()

        dx = event.xdata - self.pan_start[0]
        dy = event.ydata - self.pan_start[1]

        # Calculate new limits based on current position
        new_xlim = (cur_xlim[0] - dx, cur_xlim[1] - dx)
        new_ylim = (cur_ylim[0] - dy, cur_ylim[1] - dy)

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
        if hasattr(self, "ax_top"):
            self.ax_top.remove()
        self.ax_top = self.a.twiny()
        self.ax_top.set_xlabel("")
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

        # Determine color and elements based on element matching (if enabled and in spectroscopy mode)
        element_matches = []
        if config.spectroscopy_mode:
            if self.element_matching_enabled:
                color, element_matches = self._get_marker_color_and_elements(x_pos)
            else:
                color = "#ff0000"
        else:
            element_matches = []
            color = self.emission_line_color

        # Create vertical line
        line = self.a.axvline(
            x=x_pos, color=color, linewidth=1, linestyle="-", alpha=0.7
        )

        # Determine label based on spectroscopy mode (without units)
        if config.spectroscopy_mode:
            label_text = f"{x_pos:.2f}"
        else:
            label_text = f"{int(x_pos)}"

        # Add wavelength number annotation with styled box
        from matplotlib.transforms import blended_transform_factory

        trans = blended_transform_factory(self.a.transData, self.a.transAxes)

        label_text_obj = self.a.text(
            x_pos,
            0.98,  # 98% from bottom in axes coordinates (at the very top)
            label_text,
            rotation=0,
            verticalalignment="top",
            horizontalalignment="center",
            fontsize=9,
            color=color,
            transform=trans,
            bbox=dict(
                boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, alpha=0.9
            ),
            clip_on=True,
            animated=False,
        )

        # Add element name annotation if matches are >80%
        element_text_obj = None
        if element_matches:
            # Create multi-line label with all matching elements (sorted best to worst)
            element_labels = [elem for elem, pct in element_matches]
            element_text = "\n".join(element_labels)

            element_text_obj = self.a.text(
                x_pos,
                0.90,  # 90% from bottom in axes coordinates (below wavelength number)
                element_text,
                rotation=0,
                verticalalignment="top",
                horizontalalignment="center",
                fontsize=10,
                fontweight="bold",
                color=color,
                transform=trans,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    edgecolor=color,
                    alpha=0.9,
                ),
                clip_on=True,
                animated=False,
            )

        # Store the marker (line, label_text, x_pos, element_text_obj, label_text_obj)
        self.markers.append((line, label_text, x_pos, element_text_obj, label_text_obj))

        # Update axis ticks to include this marker
        self.update_axis_ticks()

        # Force immediate redraw to ensure marker appears at all zoom levels
        self.f.canvas.draw()
        self.f.canvas.flush_events()

    def remove_marker(self, x_pos):
        """Remove the marker closest to the specified x position"""
        if x_pos is None or not self.markers:
            return

        # Don't allow deletion when zoom or pan tool is active
        if hasattr(self.navigation_toolbar, "mode") and self.navigation_toolbar.mode:
            return

        # Find the closest marker
        closest_marker = None
        min_distance = float("inf")

        for marker in self.markers:
            line, label_text, marker_x, element_text, label_text_annotation = marker
            distance = abs(marker_x - x_pos)
            if distance < min_distance:
                min_distance = distance
                closest_marker = marker

        # Remove if within reasonable distance (1% of x-axis range)
        xlim = self.a.get_xlim()
        threshold = abs(xlim[1] - xlim[0]) * 0.01

        if closest_marker and min_distance < threshold:
            line, label_text, marker_x, element_text, label_text_annotation = (
                closest_marker
            )
            line.remove()
            if element_text:
                element_text.remove()
            if label_text_annotation:
                label_text_annotation.remove()
            self.markers.remove(closest_marker)
            self.update_axis_ticks()
            self.canvas.draw()
            self.canvas.flush_events()

    def update_axis_ticks(self):
        """Keep the secondary axis aligned without showing duplicate labels."""
        if not hasattr(self, "ax_top") or self.ax_top is None:
            return

        # Always keep limits in sync with the main axis
        self.ax_top.set_xlim(self.a.get_xlim())

        # Hide ticks/labels; annotations now handle displaying values
        self.ax_top.set_xticks([])
        self.ax_top.set_xticklabels([])

    def clear_markers(self):
        """Remove all markers"""
        for (
            line,
            label_text,
            x_pos,
            element_text,
            label_text_annotation,
        ) in self.markers:
            line.remove()
            if element_text:
                element_text.remove()
            if label_text_annotation:
                label_text_annotation.remove()
        self.markers.clear()

        # Completely clear top axis
        if hasattr(self, "ax_top"):
            self.ax_top.cla()
            self.ax_top.set_xlabel("")
            self.ax_top.set_xticks([])
            self.ax_top.set_xticklabels([])
            # Re-sync limits
            self.ax_top.set_xlim(self.a.get_xlim())

        self.canvas.draw()
        self.canvas.flush_events()

    def _load_emission_lines(self):
        """Load element emission lines from JSON file"""
        try:
            # Determine base path (works in both dev and frozen PyInstaller environments)
            if getattr(sys, "frozen", False):
                # Running as compiled executable
                base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
            else:
                # Running as script - go up one level from spectrometer/ to project root
                base_path = os.path.dirname(os.path.dirname(__file__))

            json_path = os.path.join(base_path, "element_emission_lines.json")

            with open(json_path, "r") as f:
                data = json.load(f)

            # Create list of (wavelength, element) tuples
            wavelength_elements = []
            for element, wavelengths in data.items():
                for wavelength in wavelengths:
                    wavelength_elements.append((wavelength, element))

            # Sort by wavelength
            return sorted(wavelength_elements, key=lambda x: x[0])
        except Exception as e:
            print(f"Error loading emission lines: {e}")
            return []

    def _get_marker_color_and_elements(self, wavelength):
        """Calculate marker color and element names based on proximity to known emission lines

        Returns: (color, list of (element_name, match_percentage) sorted by percentage desc)
        """
        if not self.emission_lines or not config.spectroscopy_mode:
            return ("red", [])

        # Find all emission lines and calculate match percentages
        element_matches = []

        for emission_wavelength, element in self.emission_lines:
            distance = abs(wavelength - emission_wavelength)

            # Calculate match percentage based on distance
            # Use configurable thresholds from config
            green_threshold = config.green_tolerance_nm
            yellow_threshold = config.yellow_tolerance_nm

            if distance <= green_threshold:
                # Within green tolerance: 90-100% match
                match_percentage = 100 - (distance / green_threshold) * 10
            elif distance <= yellow_threshold:
                # Within yellow tolerance: 80-90% match
                match_percentage = (
                    90
                    - (
                        (distance - green_threshold)
                        / (yellow_threshold - green_threshold)
                    )
                    * 10
                )
            else:
                # Beyond yellow tolerance, skip this element
                continue

            # Only include matches >= 80%
            if match_percentage >= 80:
                element_matches.append((element, match_percentage, distance))

        # Sort by match percentage (highest first), then by distance if tied
        element_matches.sort(key=lambda x: (-x[1], x[2]))

        # Determine color based on best match percentage
        if element_matches:
            best_match = element_matches[0][1]
            if best_match >= 90:
                color = "green"
            else:  # >= 80
                color = "#ffc200"

            # Return color and list of (element, percentage) tuples
            return (color, [(elem, pct) for elem, pct, _ in element_matches])
        else:
            return ("red", [])

    def update_marker_colors(self, enabled):
        """Update marker colors based on element matching setting"""
        self.element_matching_enabled = enabled

        # Update colors even if not in spectroscopy mode (to reset to red)
        if not self.markers:
            return

        ylim = self.a.get_ylim()

        for i, (
            line,
            label_text,
            x_pos,
            old_element_text,
            old_label_text_obj,
        ) in enumerate(self.markers):
            # Remove old element text if it exists
            if old_element_text:
                old_element_text.remove()
            # Remove old label text if it exists
            if old_label_text_obj:
                old_label_text_obj.remove()

            # Calculate new color and elements
            element_text_obj = None
            if config.spectroscopy_mode:
                if enabled:
                    color, element_matches = self._get_marker_color_and_elements(x_pos)

                    # Add element names if matches >80%
                    if element_matches:
                        element_labels = [elem for elem, pct in element_matches]
                        element_text = "\n".join(element_labels)

                        from matplotlib.transforms import blended_transform_factory

                        trans = blended_transform_factory(
                            self.a.transData, self.a.transAxes
                        )

                        element_text_obj = self.a.text(
                            x_pos,
                            0.90,
                            element_text,
                            rotation=0,
                            verticalalignment="top",
                            horizontalalignment="center",
                            fontsize=10,
                            fontweight="bold",
                            color=color,
                            transform=trans,
                            bbox=dict(
                                boxstyle="round,pad=0.3",
                                facecolor="white",
                                edgecolor=color,
                                alpha=0.9,
                            ),
                            clip_on=True,
                            animated=False,
                        )
                else:
                    color = "#ff0000"
            else:
                color = self.emission_line_color

            line.set_color(color)

            # Recreate label text annotation with new color
            from matplotlib.transforms import blended_transform_factory

            trans = blended_transform_factory(self.a.transData, self.a.transAxes)

            label_text_obj = self.a.text(
                x_pos,
                0.98,
                label_text,
                rotation=0,
                verticalalignment="top",
                horizontalalignment="center",
                fontsize=9,
                color=color,
                transform=trans,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    edgecolor=color,
                    alpha=0.9,
                ),
                clip_on=True,
                animated=False,
            )

            # Update marker with new element text and label text
            self.markers[i] = (
                line,
                label_text,
                x_pos,
                element_text_obj,
                label_text_obj,
            )

        self.canvas.draw()
        self.canvas.flush_events()
        self.canvas.flush_events()

    def save_spectrum_image(self):
        """Export spectrum visualization as an image file - replaces toolbar save"""
        from tkinter import filedialog, messagebox
        import numpy as np

        try:
            # Check if we're in spectroscopy mode
            if not config.spectroscopy_mode:
                messagebox.showinfo(
                    "Spectroscopy Mode Required",
                    "Please enable Spectroscopy Mode to export spectrum images.",
                    parent=self.master,
                )
                return

            # Get currently plotted data from the axes instead of config
            # This ensures baseline subtraction and other modifications are included
            lines = self.a.get_lines()
            if not lines:
                messagebox.showwarning(
                    "No Data", "No spectrum data to export.", parent=self.master
                )
                return

            # Find the main spectrum line (first non-comparison line)
            main_line = None
            for line in lines:
                label = line.get_label()
                # Skip comparison data and regression lines
                if label and (
                    "comparison" not in label.lower()
                    and "interpolated" not in label.lower()
                ):
                    main_line = line
                    break

            if main_line is None:
                main_line = lines[0]  # Fallback to first line

            # Extract wavelengths and intensities from the plotted line
            wavelengths = main_line.get_xdata()
            intensities = main_line.get_ydata()

            # Ask user for filename
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                title="Export Spectrum Image",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                parent=self.master,
            )

            if not filename:
                return

            # Import and generate spectrum image
            from spectrometer.spectrum_image_export import save_spectrum_image

            # Use bar mode with nanometer scale at high resolution
            save_spectrum_image(
                wavelengths,
                intensities,
                filename,
                width=2400,
                height=300,
                bar_mode=True,
            )

            messagebox.showinfo(
                "Export Successful",
                f"Spectrum image saved to:\n{filename}",
                parent=self.master,
            )

        except Exception as e:
            messagebox.showerror(
                "Export Failed",
                f"Could not export spectrum image:\n{str(e)}",
                parent=self.master,
            )
            print(f"Spectrum export error: {e}")
            import traceback

            traceback.print_exc()
