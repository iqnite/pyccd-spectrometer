import numpy as np

# serial definitions
port = "COM5"
baudrate = 115200
saved_firmware = "STM32F40x"

# Data as the program handles
SHperiod = np.uint32(200)
ICGperiod = np.uint32(100000)
AVGn = np.array([0, 1], dtype=np.uint8)
MCLK = 2000000
SHsent = np.uint32(200)
ICGsent = np.uint32(100000)
stopsignal = 0

# Data arrays for received bytes
rxData8 = np.zeros(7388, dtype=np.uint8)
rxData16 = np.zeros(3694, dtype=np.uint16)
pltData16 = np.zeros(3694, dtype=np.uint16)

# Arrays for data to transmit
txsh = np.array([0, 0, 0, 0], dtype=np.uint8)
txicg = np.array([0, 0, 0, 0], dtype=np.uint8)
txfull = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)

# Invert data
datainvert = 1
offset = 0
balanced = 0
# Mirror data left/right
datamirror = 0

# Spectroscopy mode configuration
spectroscopy_mode = False  # False = regular mode, True = spectroscopy mode
CALIBRATION_COEFF = [0, 1, 0, 0]  # fallback linear

# Emission line matching tolerance (in nm)
green_tolerance_nm = 0.3  # Lines within this distance show as green (90-100% match)
yellow_tolerance_nm = 3.0  # Lines within this distance show as yellow (80-89% match)

min_sh = 20
max_sh = 4294967295
