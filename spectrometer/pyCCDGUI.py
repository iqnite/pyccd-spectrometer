import tkinter as tk
import queue

from spectrometer import CCDmenusetup, CCDpanelsetup, CCDplots


def main():
    root = tk.Tk()
    root.title("The Otter pyCCDGUI")

    # Fullscreen setup
    root.attributes("-fullscreen", True)

    # Add Escape key to exit fullscreen
    def quit_fullscreen(event=None):
        root.attributes("-fullscreen", False)

    root.bind("<Escape>", quit_fullscreen)

    SerQueue = queue.Queue()

    # Build menu, plot frame, and control panel
    menu = CCDmenusetup.buildmenu(root)
    CCDplot = CCDplots.buildplot(root)
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
