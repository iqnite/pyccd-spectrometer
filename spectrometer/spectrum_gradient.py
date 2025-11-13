import numpy as np


def _wavelength_to_rgb(wavelength):
    """Return saturated sRGB tuple with smooth fade at spectrum edges."""
    if wavelength < 380 or wavelength > 780:
        return (0.0, 0.0, 0.0)

    if wavelength < 440:
        r = -(wavelength - 440) / (440 - 380)
        g = 0.0
        b = 1.0
    elif wavelength < 490:
        r = 0.0
        g = (wavelength - 440) / (490 - 440)
        b = 1.0
    elif wavelength < 510:
        r = 0.0
        g = 1.0
        b = -(wavelength - 510) / (510 - 490)
    elif wavelength < 580:
        r = (wavelength - 510) / (580 - 510)
        g = 1.0
        b = 0.0
    elif wavelength < 645:
        r = 1.0
        g = -(wavelength - 645) / (645 - 580)
        b = 0.0
    else:
        r = 1.0
        g = 0.0
        b = 0.0

    if wavelength < 420:
        factor = (wavelength - 380) / (420 - 380)
    elif wavelength > 700:
        factor = (780 - wavelength) / (780 - 700)
    else:
        factor = 1.0

    gamma = 0.8
    factor = max(factor, 0.0)
    r = (max(r, 0.0) * factor) ** gamma
    g = (max(g, 0.0) * factor) ** gamma
    b = (max(b, 0.0) * factor) ** gamma

    return (r, g, b)


def add_spectrum_gradient(ax, x_min, x_max, y_min, y_max):
    """Render a high-resolution spectrum gradient as an image background."""
    span = max(x_max - x_min, 1e-9)
    max_samples = 2048
    samples = max(256, min(max_samples, int(span / 2)))
    x_values = np.linspace(x_min, x_max, samples)
    colours = np.array([_wavelength_to_rgb(x) for x in x_values])

    # Ensure a fade-to-black on the red side even if 780 nm isn't visible.
    # If the right edge is within the red region (>700 nm), fade the last ~40 nm to black.
    if x_max > 700:
        fade_nm = 40.0
        right_start = max(700.0, x_max - fade_nm)
        denom = max(x_max - right_start, 1e-9)
        fade = np.ones_like(x_values)
        mask = x_values >= right_start
        fade[mask] = (x_max - x_values[mask]) / denom
        colours = colours * fade[:, None]

    # Duplicate row so imshow gets a 2xN image we can stretch vertically
    gradient = np.repeat(colours[np.newaxis, :, :], 2, axis=0)

    image = ax.imshow(
        gradient,
        extent=(x_min, x_max, y_min, y_max),
        origin="lower",
        aspect="auto",
        regression="bilinear",
        alpha=0.6,
        zorder=-1,
    )
    image._spectrum_background = True


def update_spectrum_background(ax, spectroscopy_mode, show_colors):
    """Update the spectrum background based on mode and checkbox state."""
    # Always remove existing spectrum overlays first
    for patch in ax.patches[:]:
        if hasattr(patch, "_spectrum_background"):
            patch.remove()

    for image in ax.images[:]:
        if hasattr(image, "_spectrum_background"):
            image.remove()

    if spectroscopy_mode and show_colors:
        if not hasattr(ax, "_spectrum_original_facecolor"):
            ax._spectrum_original_facecolor = ax.get_facecolor()
        ax.set_facecolor("black")
        # Use current x-axis limits but fixed y-axis range for intensity
        xlim = ax.get_xlim()
        add_spectrum_gradient(ax, xlim[0], xlim[1], -20000, 20000)
    else:
        if hasattr(ax, "_spectrum_original_facecolor"):
            ax.set_facecolor(ax._spectrum_original_facecolor)
