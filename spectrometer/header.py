"""
Top panel for the spectrometer GUI
"""

import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


class HeaderPanel(ttk.Frame):
    def __init__(self, master, CCDplot, SerQueue):
        super().__init__(master)

        # Store CCDplot reference for callbacks
        self.CCDplot = CCDplot

        self.logo_display()
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
