"""
Additional widgets for the spectrometer UI.
"""

import tkinter as tk
from tkinter import ttk


class CollapsibleTTK(ttk.Frame):
    def __init__(self, parent, title, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.show = tk.BooleanVar()
        self.show.set(True)

        self.header = ttk.Frame(self)
        self.header.pack(fill="x", expand=1)

        self.title = title
        self.toggle_button = ttk.Checkbutton(
            self.header,
            text="v " + title,
            variable=self.show,
            command=self.toggle,
            style="Toolbutton",
        )
        self.toggle_button.pack(side="left", fill="x")

        self.sub_frame = ttk.Frame(self)
        self.sub_frame.pack(fill="both", expand=1)

    def toggle(self):
        if self.show.get():
            self.sub_frame.pack(fill="both", expand=1)
            self.toggle_button.config(text="v " + self.title)
        else:
            self.sub_frame.forget()
            self.toggle_button.config(text="> " + self.title)
