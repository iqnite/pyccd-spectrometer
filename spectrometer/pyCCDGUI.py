import tkinter as tk
import queue
import os
import sys
from typing import cast
from PIL import Image, ImageTk

import sv_ttk
from spectrometer import CCDpanelsetup, CCDplots

root = tk.Tk()
root.title("pySPEC")


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


def enter_fullscreen(event=None):
    root.attributes("-fullscreen", True)


def quit_fullscreen(event=None):
    root.attributes("-fullscreen", False)


root.bind("<F11>", enter_fullscreen)
root.bind("<Escape>", quit_fullscreen)

enter_fullscreen()

SerQueue = queue.Queue()

CCDplot = CCDplots.BuildPlot(root)
panel_container = tk.Frame(root)
canvas = tk.Canvas(panel_container, highlightthickness=0)
scrollbar = tk.Scrollbar(panel_container, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

panel = CCDpanelsetup.BuildPanel(scrollable_frame, CCDplot, SerQueue)
panel.pack(fill="both", expand=True)

scrollable_frame.bind(
    "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")


def _on_mousewheel(event):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


canvas.bind("<MouseWheel>", _on_mousewheel)
for child in scrollable_frame.winfo_children():
    child.bind("<MouseWheel>", _on_mousewheel)

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)  # Plot column expands
root.grid_columnconfigure(1, weight=0)  # Panel column fixed

CCDplot.grid(row=0, column=0, sticky="nsew")
panel_container.grid(row=0, column=1, sticky="ns", padx=(35, 0))


def main():
    root.mainloop()


if __name__ == "__main__":
    main()
