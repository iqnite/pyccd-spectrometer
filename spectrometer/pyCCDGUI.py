import tkinter as tk
import queue
import os
import sys
from typing import cast
from PIL import Image, ImageTk

import spectrometer.sidebar
import sv_ttk
from spectrometer import CCDplots, configuration

root = tk.Tk()
root.title("AstroLens pySPEC")


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundles.

    When frozen by PyInstaller, data files are unpacked to a temp folder
    available via sys._MEIPASS. Otherwise, use the current working directory.
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


icon = Image.open(resource_path("assets/icon.png"))
icon = icon.resize((1024, 1024))
icon_tk = ImageTk.PhotoImage(icon)
root.iconphoto(True, cast(tk.PhotoImage, icon_tk))
root.state("zoomed")
sv_ttk.set_theme("dark")

SerQueue = queue.Queue()

CCDplot = CCDplots.BuildPlot(root, configuration.Config())
CCDplot.grid(row=0, column=0, sticky="nsew")
side_bar = spectrometer.sidebar.SideBar(root, CCDplot, SerQueue)
side_bar.grid(row=0, column=2, sticky="nsew")
side_bar.panel_container.pack(fill="y", side="bottom", expand=True)

root.bind("<F11>", side_bar.header.enter_fullscreen)
root.bind("<Escape>", side_bar.header.quit_fullscreen)

side_bar.header.enter_fullscreen()


def main():
    root.mainloop()


if __name__ == "__main__":
    main()
