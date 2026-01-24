import numpy as np


class Config:
    def __init__(self):
        # serial definitions
        self.port = "COM5"
        self.baudrate = 115200
        self.saved_firmware = "STM32F40x"

        # Data as the program handles
        self.sh_period = np.uint32(200)
        self.icg_period = np.uint32(100000)
        self.avg_n = np.array([0, 1], dtype=np.uint8)
        self.mclk = 2000000
        self.sh_sent = np.uint32(200)
        self.icg_sent = np.uint32(100000)
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
        self.calibration_coeffs = [0, 1, 0, 0]  # fallback linear

        # Emission line matching tolerance (in nm)
        self.green_tolerance_nm = (
            0.3  # Lines within this distance show as green (90-100% match)
        )
        self.yellow_tolerance_nm = (
            3.0  # Lines within this distance show as yellow (80-89% match)
        )

        self.min_sh = 20
        self.max_sh = 4294967295

    @property
    def SHperiod(self):
        return self.sh_period

    @SHperiod.setter
    def SHperiod(self, value):
        self.sh_period = value

    @property
    def ICGperiod(self):
        return self.icg_period

    @ICGperiod.setter
    def ICGperiod(self, value):
        self.icg_period = value

    @property
    def AVGn(self):
        return self.avg_n

    @AVGn.setter
    def AVGn(self, value):
        self.avg_n = value

    @property
    def MCLK(self):
        return self.mclk

    @MCLK.setter
    def MCLK(self, value):
        self.mclk = value

    @property
    def SHsent(self):
        return self.sh_sent

    @SHsent.setter
    def SHsent(self, value):
        self.sh_sent = value

    @property
    def ICGsent(self):
        return self.icg_sent

    @ICGsent.setter
    def ICGsent(self, value):
        self.icg_sent = value

    @property
    def CALIBRATION_COEFF(self):
        return self.calibration_coeffs

    @CALIBRATION_COEFF.setter
    def CALIBRATION_COEFF(self, value):
        self.calibration_coeffs = value
