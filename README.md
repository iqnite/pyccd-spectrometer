# pySPEC

![Astrolens Logo](assets/AstroLens.svg)

pySPEC is a platform-independent graphical user-interface written in Python 3 for spectroscopy with the TCD1304. Originally developed by [Esben Rossel](https://tcd1304.wordpress.com) for general-purpose data acquisition with the TCD1304 linear CCD sensor, it has been modified by [Adrian Matsch](https://www.astrolens.net) to specifically support spectroscopy applications.

## Installation

On Windows and macOS, download and run the installer (.exe or .dmg) from the [**Releases**](https://github.com/iqnite/pyccd-spectrometer/releases/latest) page.

On other platforms, ensure you have Python 3 and the required dependencies installed. You can install the dependencies using pipenv:

```bash
python3 -m pip install --user pipenv
pipenv install
```

After that, you can run the application using:

```bash
pipenv run python3 main.pyw
```

## NIST line catalog (offline)

pySPEC can match detected peaks against an offline line catalog derived from the NIST Atomic Spectra Database (ASD).

- Default catalog file: `nist_line_catalog.json`
- Regenerate/update the catalog (downloads from NIST ASD and writes the JSON file):

```bash
python3 scripts/import_nist_asd_lines.py --from-legacy --low-nm 350 --upp-nm 750 --output nist_line_catalog.json
```

## Utils

In the utils folder one can find a script named "plotgraph.py". This file can be used to open the .dat files which are generated when saving a graph via pySPEC. It creates a new folder at the lcoation of the .dat file, which includes a .csv file aswell as a .png of the plotted graphs.

## Credits

- Original development by [Esben Rossel](https://tcd1304.wordpress.com)
- Modifications for spectroscopy and design by [Adrian Matsch](https://www.astrolens.net)
- Development supported by [Philipp Donà](https://iqnite.github.io/)
