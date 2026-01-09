"""
Generate spectrum images on black background from intensity and wavelength data.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from spectrometer.spectrum_gradient import _wavelength_to_rgb


def generate_spectrum_image(wavelengths, intensities, width=1200, height=200, normalize=True):
    """
    Generate a spectrum image showing colored bands based on wavelength and intensity.
    
    Args:
        wavelengths: Array of wavelength values (nm)
        intensities: Array of intensity values
        width: Output image width in pixels
        height: Output image height in pixels
        normalize: If True, normalize intensities to 0-1 range
        
    Returns:
        PIL Image object with spectrum visualization
    """
    # Create black background
    img_array = np.zeros((height, width, 3), dtype=np.float32)
    
    # Normalize intensities if requested
    if normalize:
        intensities = np.array(intensities, dtype=np.float32)
        int_min = intensities.min()
        int_max = intensities.max()
        if int_max > int_min:
            intensities = (intensities - int_min) / (int_max - int_min)
        else:
            intensities = np.ones_like(intensities) * 0.5
    else:
        intensities = np.clip(intensities, 0.0, 1.0)
    
    # Get wavelength range
    wl_min = wavelengths.min()
    wl_max = wavelengths.max()
    wl_span = max(wl_max - wl_min, 1e-9)
    
    # Map each data point to a column in the image
    for i, (wl, intensity) in enumerate(zip(wavelengths, intensities)):
        # Calculate column position
        col = int((wl - wl_min) / wl_span * (width - 1))
        col = np.clip(col, 0, width - 1)
        
        # Get color for this wavelength
        rgb = _wavelength_to_rgb(wl)
        
        # Apply intensity scaling
        rgb_scaled = tuple(c * intensity for c in rgb)
        
        # Fill the column with this color
        img_array[:, col] = rgb_scaled
    
    # Apply slight horizontal blur for smooth transitions
    from scipy.ndimage import gaussian_filter1d
    for channel in range(3):
        img_array[:, :, channel] = gaussian_filter1d(img_array[:, :, channel], sigma=1.5, axis=1)
    
    # Convert to 8-bit image
    img_array = np.clip(img_array * 255, 0, 255).astype(np.uint8)
    
    return Image.fromarray(img_array)


def generate_spectrum_bar(wavelengths, intensities, width=2400, height=300, normalize=True):
    """
    Generate spectrum bar with nanometer scale showing the emission spectrum.
    
    With 3694 pixels across ~200nm range, we have very high resolution (~0.05nm per pixel).
    The data is sharp enough to show individual emission lines clearly.
    
    Args:
        wavelengths: Array of wavelength values (nm) - typically 3694 data points
        intensities: Array of intensity values
        width: Output image width in pixels (default 2400 for high resolution)
        height: Output bar height in pixels (includes scale at top)
        normalize: If True, normalize intensities to 0-1 range
        
    Returns:
        PIL Image object with spectrum bar and nanometer scale
    """
    # Reserve space for scale at top (proportional to height)
    scale_height = 60  # Doubled from 30
    spectrum_height = height - scale_height
    
    # Create black background
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Normalize intensities if requested
    if normalize:
        intensities = np.array(intensities, dtype=np.float32)
        int_min = intensities.min()
        int_max = intensities.max()
        if int_max > int_min:
            intensities = (intensities - int_min) / (int_max - int_min)
        else:
            intensities = np.ones_like(intensities) * 0.5
    else:
        intensities = np.clip(intensities, 0.0, 1.0)
    
    # Get wavelength range
    wl_min = wavelengths.min()
    wl_max = wavelengths.max()
    wl_span = max(wl_max - wl_min, 1e-9)
    
    # Calculate data resolution
    data_points = len(wavelengths)
    nm_per_pixel_data = wl_span / data_points if data_points > 0 else 1.0
    pixels_per_nm_output = width / wl_span
    
    print(f"Spectrum export info:")
    print(f"  Data points: {data_points}")
    print(f"  Wavelength range: {wl_min:.2f} - {wl_max:.2f} nm ({wl_span:.2f} nm span)")
    print(f"  Data resolution: {nm_per_pixel_data:.4f} nm/pixel")
    print(f"  Output resolution: {pixels_per_nm_output:.2f} pixels/nm")
    
    # Since we have ~3694 data points across ~200nm, that's ~18 data points per nm.
    # The output is 1200 pixels across ~200nm = 6 pixels per nm.
    # So we're downsampling, and should preserve sharp peaks by finding the brightest
    # data point that contributes to each output column.
    
    # Create spectrum bar - for each output column, find the brightest contributing data point
    spectrum_array = np.zeros((spectrum_height, width, 3), dtype=np.float32)
    
    # Track which data points contribute to each column and their intensities
    column_contributors = [[] for _ in range(width)]
    
    for i, (wl, intensity) in enumerate(zip(wavelengths, intensities)):
        col = int((wl - wl_min) / wl_span * (width - 1))
        col = np.clip(col, 0, width - 1)
        column_contributors[col].append((i, intensity))
    
    # For each column, use the wavelength of the BRIGHTEST contributor
    for col in range(width):
        if not column_contributors[col]:
            continue
            
        # Find the brightest contributor for this column
        brightest_idx, brightest_intensity = max(column_contributors[col], key=lambda x: x[1])
        
        # Use the wavelength of the brightest point
        wl = wavelengths[brightest_idx]
        intensity = brightest_intensity
        
        rgb = _wavelength_to_rgb(wl)
        rgb_scaled = np.array(rgb) * intensity
        
        spectrum_array[:, col] = rgb_scaled
    
    # No blur - we have high-resolution data (3694 points) and want to preserve sharp lines
    # The max() accumulation already handles overlapping data points correctly
    print(f"  No blur applied - preserving sharp emission lines")
    
    # Convert spectrum to 8-bit and place in image
    spectrum_array = np.clip(spectrum_array * 255, 0, 255).astype(np.uint8)
    img_array[scale_height:, :] = spectrum_array
    
    # Create PIL image for adding scale
    img = Image.fromarray(img_array)
    draw = ImageDraw.Draw(img)
    
    # Try to load a nice font (scaled up for higher resolution)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        try:
            font = ImageFont.truetype("Arial.ttf", 24)
        except:
            font = ImageFont.load_default()
    
    # Draw wavelength scale at top with hierarchical tick marks
    # 20nm: Major ticks with labels (longest, brightest)
    # 10nm: Medium ticks (no labels)
    # 5nm: Small ticks
    # 1nm: Tiny ticks (for high-res visualization)
    
    # Draw 1nm tiny tick marks for fine resolution
    start_1nm = int(np.ceil(wl_min))
    for wl in range(start_1nm, int(wl_max) + 1, 1):
        if wl < wl_min or wl > wl_max:
            continue
            
        x_pos = int((wl - wl_min) / wl_span * (width - 1))
        
        # Determine tick type based on divisibility
        if wl % 20 == 0:
            # Major tick (20nm): longest line with label
            draw.line([(x_pos, scale_height - 30), (x_pos, scale_height - 1)], fill=(220, 220, 220), width=3)
            
            # Draw label for major ticks only
            label = f"{wl}"
            try:
                bbox = draw.textbbox((0, 0), label, font=font)
                text_width = bbox[2] - bbox[0]
            except:
                text_width = len(label) * 12
                
            text_x = x_pos - text_width // 2
            draw.text((text_x, 4), label, fill=(220, 220, 220), font=font)
        elif wl % 10 == 0:
            # Medium tick (10nm): medium line
            draw.line([(x_pos, scale_height - 20), (x_pos, scale_height - 1)], fill=(180, 180, 180), width=2)
        elif wl % 5 == 0:
            # Small tick (5nm): short line
            draw.line([(x_pos, scale_height - 12), (x_pos, scale_height - 1)], fill=(130, 130, 130), width=2)
        else:
            # Tiny tick (1nm): very short line
            draw.line([(x_pos, scale_height - 6), (x_pos, scale_height - 1)], fill=(80, 80, 80), width=1)
    
    # Add "nm" label on the right
    draw.text((width - 30, 2), "nm", fill=(200, 200, 200), font=font)
    
    return img


def save_spectrum_image(wavelengths, intensities, filename, width=1200, height=200, bar_mode=False):
    """
    Save spectrum image to file.
    
    Args:
        wavelengths: Array of wavelength values (nm)
        intensities: Array of intensity values
        filename: Output filename (PNG recommended)
        width: Output image width
        height: Output image height
        bar_mode: If True, creates a dual-bar image (reference + intensity)
    """
    if bar_mode:
        img = generate_spectrum_bar(wavelengths, intensities, width, height)
    else:
        img = generate_spectrum_image(wavelengths, intensities, width, height)
    
    img.save(filename)
    return filename
