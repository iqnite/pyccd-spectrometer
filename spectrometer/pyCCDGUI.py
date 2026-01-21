import tkinter as tk
import queue
import os
import sys
from typing import cast
from PIL import Image, ImageTk

import sv_ttk
from spectrometer import CCDpanelsetup, CCDplots, config

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

CCDplot = CCDplots.BuildPlot(root, config.Config())
panel_container = tk.Frame(root)
canvas = tk.Canvas(panel_container, highlightthickness=0)
scrollbar = tk.Scrollbar(panel_container, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

panel = CCDpanelsetup.BuildPanel(scrollable_frame, CCDplot, SerQueue)
panel.pack(fill="both", expand=True)


def update_scroll_region(event=None):
    canvas.configure(scrollregion=canvas.bbox("all"))
    # Update canvas window width to match the scrollable_frame's required width
    canvas.itemconfig(canvas_window, width=scrollable_frame.winfo_reqwidth())


scrollable_frame.bind("<Configure>", update_scroll_region)

canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

# Use grid instead of pack for better control over scrollbar placement
panel_container.grid_rowconfigure(0, weight=1)
panel_container.grid_columnconfigure(0, weight=1)
canvas.grid(row=0, column=0, sticky="nsew")
scrollbar.grid(row=0, column=1, sticky="ns")


def _on_mousewheel(event):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


canvas.bind("<MouseWheel>", _on_mousewheel)
for child in scrollable_frame.winfo_children():
    child.bind("<MouseWheel>", _on_mousewheel)

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)  # Plot column expands
root.grid_columnconfigure(1, weight=0, minsize=470)

CCDplot.grid(row=0, column=0, sticky="nsew")
panel_container.grid(
    row=0, column=1, sticky="nsew", padx=(35, 0)
)  # Changed to nsew to allow horizontal expansion


def main():
    root.mainloop()


if __name__ == "__main__":
    main()
