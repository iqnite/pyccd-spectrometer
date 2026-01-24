from PIL import Image, ImageDraw, ImageFont, ImageTk


import os
import tkinter as tk
from tkinter import ttk

from spectrometer import CCDpanelsetup


class SideBar(ttk.Frame):
    def __init__(self, master: tk.Tk | tk.Frame | ttk.Frame, CCDplot, SerQueue):
        super().__init__(master)
        self.panel_container = tk.Frame(self)
        self.canvas = tk.Canvas(self.panel_container, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self.panel_container, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = tk.Frame(self.canvas)

        # Create a separator for resizing
        self.separator = tk.Frame(
            master, bg="#555", width=4, cursor="sb_h_double_arrow"
        )
        self.separator.grid(row=0, column=1, sticky="ns")

        self.header = PanelHeader(self)
        self.panel = CCDpanelsetup.BuildPanel(self.scrollable_frame, CCDplot, SerQueue)
        self.panel.pack(fill="both", expand=True)

        self.sidebar_expand_threshold = 10
        self.sidebar_collapse_threshold = 390
        self.sidebar_visible = True

        self.separator.bind("<ButtonPress-1>", self.on_separator_press)
        self.separator.bind("<ButtonRelease-1>", self.on_separator_release)

        self.scrollable_frame.bind("<Configure>", self.update_scroll_region)

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Use grid instead of pack for better control over scrollbar placement
        self.panel_container.grid_rowconfigure(0, weight=1)
        self.panel_container.grid_columnconfigure(0, weight=1, minsize=400)
        self.panel_container.grid_columnconfigure(1, weight=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        for child in self.scrollable_frame.winfo_children():
            child.bind("<MouseWheel>", self._on_mousewheel)

        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)  # Plot column expands
        master.grid_columnconfigure(1, weight=0)  # Separator column
        master.grid_columnconfigure(2, weight=0)  # Sidebar column

        # Drag functionality for resizing
        self.drag_data = {"x": 0, "dragging": False}

    def update_scroll_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Update canvas window width to match the scrollable_frame's required width
        self.canvas.itemconfig(
            self.canvas_window, width=self.scrollable_frame.winfo_reqwidth()
        )

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_separator_press(self, event):
        self.drag_data["x"] = event.x_root
        self.drag_data["dragging"] = True
        self.separator.config(bg="#888")

    def on_separator_release(self, event):
        self.drag_data["dragging"] = False
        self.separator.config(bg="#555")

        delta_x = event.x_root - self.drag_data["x"]
        self.drag_data["x"] = event.x_root
        current_width = self.winfo_width()
        new_width = current_width - delta_x
        if self.sidebar_visible:
            if new_width < self.sidebar_collapse_threshold:
                self.sidebar_visible = False
                self.grid_remove()
        else:
            if new_width > self.sidebar_expand_threshold:
                self.sidebar_visible = True
                self.grid(row=0, column=2, sticky="nsew")


class PanelHeader(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.header_fields()

    def header_fields(self):
        """Add header, logo, and close button"""
        # Add AstroLens logo on the left
        try:
            # Get the path to the PNG file
            logo_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "assets", "astrolens.png"
            )

            if os.path.exists(logo_path):
                logo_image = Image.open(logo_path)

                # Calculate proper aspect ratio resize for header
                target_height = 45  # Increased from 30 for larger logo
                aspect_ratio = logo_image.width / logo_image.height
                target_width = int(target_height * aspect_ratio)

                logo_image = logo_image.resize(
                    (target_width, target_height), Image.Resampling.LANCZOS
                )
                logo_photo = ImageTk.PhotoImage(logo_image)

                self.logo_label = ttk.Label(self, image=logo_photo)
                self.logo_label.image = logo_photo  # type: ignore Keep a reference
                self.logo_label.grid(row=0, column=0, pady=10, padx=(5, 0), sticky="w")
        except Exception as e:
            print(f"Could not load logo: {e}")

        # Create circular close button with high resolution
        button_size = 30
        scale = 4  # Render at 4x resolution for smooth edges
        high_res_size = button_size * scale

        # Create high-resolution image
        self.button_img = Image.new(
            "RGBA", (high_res_size, high_res_size), (0, 0, 0, 0)
        )
        draw = ImageDraw.Draw(self.button_img, "RGBA")

        # Draw smooth circle
        draw.ellipse([0, 0, high_res_size - 1, high_res_size - 1], fill="#ffc200")

        # Draw X text - use simple X instead of unicode
        try:
            font = ImageFont.truetype("arial.ttf", int(16 * scale))
        except:
            try:
                font = ImageFont.truetype("Arial.ttf", int(16 * scale))
            except:
                font = None

        text = "X"
        text_x = 0
        text_y = 0
        padding = 0
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (high_res_size - text_width) // 2 - bbox[0]
            text_y = (high_res_size - text_height) // 2 - bbox[1]
            draw.text((text_x, text_y), text, fill="black", font=font)
        else:
            # Fallback: draw X as two lines
            padding = high_res_size // 4
            draw.line(
                [
                    (padding, padding),
                    (high_res_size - padding, high_res_size - padding),
                ],
                fill="black",
                width=scale * 2,
            )
            draw.line(
                [
                    (high_res_size - padding, padding),
                    (padding, high_res_size - padding),
                ],
                fill="black",
                width=scale * 2,
            )

        # Scale down for smooth anti-aliased result
        self.button_img = self.button_img.resize(
            (button_size, button_size), Image.Resampling.LANCZOS
        )
        self.button_photo = ImageTk.PhotoImage(self.button_img)

        # Create hover version (darker)
        self.button_img_hover = Image.new(
            "RGBA", (high_res_size, high_res_size), (0, 0, 0, 0)
        )
        draw_hover = ImageDraw.Draw(self.button_img_hover, "RGBA")
        draw_hover.ellipse([0, 0, high_res_size - 1, high_res_size - 1], fill="#e6ad00")

        if font:
            draw_hover.text((text_x, text_y), text, fill="black", font=font)
        else:
            draw_hover.line(
                [
                    (padding, padding),
                    (high_res_size - padding, high_res_size - padding),
                ],
                fill="black",
                width=scale * 2,
            )
            draw_hover.line(
                [
                    (high_res_size - padding, padding),
                    (padding, high_res_size - padding),
                ],
                fill="black",
                width=scale * 2,
            )

        self.button_img_hover = self.button_img_hover.resize(
            (button_size, button_size), Image.Resampling.LANCZOS
        )
        self.button_photo_hover = ImageTk.PhotoImage(self.button_img_hover)

        # Get background color
        try:
            style = ttk.Style()
            bg_color = style.lookup("TFrame", "background")
            if not bg_color:
                bg_color = "#1c1c1c"
        except:
            bg_color = "#1c1c1c"

        # Create canvas with the button image
        self.bclose = tk.Canvas(
            self,
            width=button_size,
            height=button_size,
            highlightthickness=0,
            bg=bg_color,
        )

        self.button_image_id = self.bclose.create_image(
            button_size // 2, button_size // 2, image=self.button_photo
        )

        # Bind hover and click events
        self.bclose.bind("<Enter>", self.on_close_hover)
        self.bclose.bind("<Leave>", self.on_close_leave)
        self.bclose.bind("<Button-1>", lambda e: self.winfo_toplevel().destroy())
        self.bclose.config(cursor="hand2")

        # Configure grid columns to allow button placement
        self.grid_columnconfigure(0, weight=0)  # Logo column
        self.grid_columnconfigure(1, weight=1)  # Spacer column
        self.grid_columnconfigure(2, weight=0)  # Close button column

        self.bclose.grid(row=0, column=2, pady=10, padx=(0, 10), sticky="e")

    def on_close_hover(self, event):
        """Change color on hover"""
        self.bclose.itemconfig(self.button_image_id, image=self.button_photo_hover)

    def on_close_leave(self, event):
        """Restore color when not hovering"""
        self.bclose.itemconfig(self.button_image_id, image=self.button_photo)

    def enter_fullscreen(self, event=None):
        self.winfo_toplevel().attributes("-fullscreen", True)
        self.pack(fill="x", side="top", expand=False)
        self.update()

    def quit_fullscreen(self, event=None):
        self.winfo_toplevel().attributes("-fullscreen", False)
        self.pack_forget()
        self.master.update()
