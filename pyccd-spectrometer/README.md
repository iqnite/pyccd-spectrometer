# pyCCD Spectrometer Kivy Application

## Overview
The pyCCD Spectrometer is a Kivy-based application designed for controlling and visualizing data from a CCD spectrometer. This application maintains the functionality of the original Python program while providing a modern interface suitable for horizontal medium-sized Android phones.

## Project Structure
The project is organized as follows:

```
pyccd-spectrometer
├── src
│   ├── main.py                # Entry point for the Kivy application
│   ├── spectrometer
│   │   └── pyCCDGUI.py        # Contains the existing functionality of the spectrometer
│   └── ui
│       ├── __init__.py        # Initializes the UI package
│       ├── main_screen.kv     # Kivy layout for the main screen
│       └── widgets.kv         # Kivy layout for additional custom widgets
├── buildozer.spec             # Configuration for building the Kivy application for Android
├── requirements.txt           # Lists dependencies for the Kivy application
├── main.pyw                   # Original Python program for the spectrometer GUI
└── README.md                   # Documentation for the project
```

## Installation
To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd pyccd-spectrometer
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Build the application for Android using Buildozer:
   ```
   buildozer -v android debug
   ```

## Usage
To run the application on your local machine, execute the following command:
```
python src/main.py
```

For Android, install the generated APK on your device and launch the application.

## Contributing
Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.