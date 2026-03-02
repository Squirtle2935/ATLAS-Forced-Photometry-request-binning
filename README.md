# ATLAS Forced Photometry Pipeline

A fully automated Python pipeline to download, clean, bin, and visualize forced photometry light curves from the [ATLAS (Asteroid Terrestrial-impact Last Alert System)](https://fallingstar-data.com/forcedphot/) server.

## Prerequisites

Ensure you have Python 3 installed. You can install all required libraries in one go using the provided `requirements.txt` file:

```bash
pip install -r requirements.txt
```

*Note: You must have a registered account on the ATLAS Forced Photometry server.*

## Authentication Setup (Important)

Before running the script, you must create a file named `.env` in the same directory as the script to store your ATLAS login credentials securely. 

Create a `.env` file and add the following two lines:
```text
ATLAS_USERNAME=your_username_here
ATLAS_PASSWORD=your_password_here
```

## Usage

Run the script from your terminal using command-line arguments. 

| Argument | Status | Description | Example |
| :--- | :--- | :--- | :--- |
| `--name` | **Required** | The name of the astronomical object. Used for output filenames and plot titles. | e.g. `SN2024ggi` |
| `--ra` | **Required** | Right Ascension. Accepts both Sexagesimal (HMS) and Decimal Degrees formats. | e.g.`"11:18:22.087"` or `169.592030529` |
| `--dec` | **Required** | Declination. Accepts both DMS and Decimal Degrees formats. *(See important note below for negative values).* | `-32:50:15.27` or `-32.8375756395` |
| `--mjd_min` | **Required** | The minimum Modified Julian Date (MJD) to start fetching data. | `60411.0` |
| `--mjd_max` | Optional | The maximum MJD to fetch data up to. If left blank, it fetches the latest available data. | `61000.0` |

```bash
python atlas_fp_request.py --name <ObjectName> --ra <RA> --dec <DEC> --mjd_min <Start_MJD> [--mjd_max <End_MJD>]
```

### Example Command

```bash
python atlas_fp_request.py --name SN2024ggi --ra 11:18:22.087 --dec=-32:50:15.27 --mjd_min 60411.0
```

> **⚠️ IMPORTANT NOTE FOR NEGATIVE DECLINATION:** > If your target has a negative Declination (e.g., `-00:26:43.28`), you **must** use an equals sign (`=`) between `--dec` and the value. Otherwise, the command-line parser will mistake the minus sign for a new argument flag.


### Interactive Workflow

1. **Login:** The script will securely ask for your ATLAS username and password.
2. **Download:** It will queue the task, wait for the ATLAS server to process it, and save the raw data (`<ObjectName>_LC.txt`).
3. **Process & Plot:** The script will pause and ask:
   `Do you want to perform daily binning and plot the light curve for SN2025wiu? (y/n):`
   Type `y` to automatically execute the data cleaning, binning, and plotting routines.


## Output Files

The pipeline will generate three files in the same directory:
1. `<ObjectName>_LC.txt`: The raw data retrieved directly from ATLAS.
2. `<ObjectName>_binned_LC.txt`: The processed, cleaned, and daily-binned data.
3. `<ObjectName>_LC.png`: The final combined light curve plot (Magnitude and Flux).