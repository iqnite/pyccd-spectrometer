import numpy as np


class Config:
    def __init__(self):
        # serial definitions
        self.port = "COM5"
        self.baudrate = 115200
        self.saved_firmware = "STM32F40x"

        # Data as the program handles
        self.SHperiod = np.uint32(200)
        self.ICGperiod = np.uint32(100000)
        self.AVGn = np.array([0, 1], dtype=np.uint8)
        self.MCLK = 2000000
        self.SHsent = np.uint32(200)
        self.ICGsent = np.uint32(100000)
        self.stopsignal = 0

        # Data arrays for received bytes
        self.rxData8 = np.zeros(7388, dtype=np.uint8)
        self.rxData16 = np.zeros(3694, dtype=np.uint16)
        self.pltData16 = np.zeros(3694, dtype=np.uint16)

        # Arrays for data to transmit
        self.txsh = np.array([0, 0, 0, 0], dtype=np.uint8)
        self.txicg = np.array([0, 0, 0, 0], dtype=np.uint8)
        self.txfull = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)

        # Invert data
        self.datainvert = 1
        self.offset = 0
        self.balanced = 0
        # Mirror data left/right
        self.datamirror = 0

        # Spectroscopy mode configuration
        self.spectroscopy_mode = False  # False = regular mode, True = spectroscopy mode
        self.CALIBRATION_COEFF = [0, 1, 0, 0]  # fallback linear

        # Emission line matching tolerance (in nm)
        self.green_tolerance_nm = (
            0.3  # Lines within this distance show as green (90-100% match)
        )
        self.yellow_tolerance_nm = (
            3.0  # Lines within this distance show as yellow (80-89% match)
        )

        self.min_sh = 20
        self.max_sh = 4294967295
