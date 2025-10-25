import tkinter as tk
import queue

import sv_ttk
from spectrometer import CCDpanelsetup, CCDplots


def main():
    root = tk.Tk()
    root.title("pySPEC")
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

    # Build menu, plot frame, and control panel
    CCDplot = CCDplots.BuildPlot(root)
    panel = CCDpanelsetup.BuildPanel(root, CCDplot, SerQueue)

    # Configure root window for expansion
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)  # Plot column expands
    root.grid_columnconfigure(1, weight=0)  # Panel column fixed

    # Place widgets with proper expansion
    CCDplot.grid(row=0, column=0, sticky="nsew")
    panel.grid(row=0, column=1, sticky="ns")

    root.mainloop()


if __name__ == "__main__":
    main()
