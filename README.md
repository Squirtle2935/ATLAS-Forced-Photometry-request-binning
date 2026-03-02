# ATLAS Forced Photometry request and binning

A fully automated Python pipeline to download, clean, bin, and visualize forced photometry light curves from the [ATLAS (Asteroid Terrestrial-impact Last Alert System)](https://fallingstar-data.com/forcedphot/) server.

## Installation

First, clone the repository to your local machine and navigate into the project directory:

```bash
git clone https://github.com/Squirtle2935/ATLAS-Forced-Photometry-request-binning.git
cd ATLAS-Forced-Photometry-request-binning.git
```

Next, ensure you have Python 3 installed. Install all required libraries in one go using the provided `requirements.txt` file:

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

You can run this pipeline in two ways: **Single Target Mode** or **Batch Processing Mode**.

### 1. Single Target Mode
Run the script directly from your terminal by providing the object's details.

```bash
python atlas_fp_request.py --name SN2024ggi --ra 11:18:22.087 --dec=-32:50:15.27 --mjd_min 60411.0 --mjd_max 60511.0
```

> [!WARNING]
> **IMPORTANT NOTE FOR NEGATIVE DECLINATION:** If your target has a negative Declination (e.g., `-00:26:43.28`), you **must** use an equals sign (`=`) between `--dec` and the value. Otherwise, the command-line parser will mistake the minus sign for a new argument flag.

### 2. Batch Processing Mode
You can process multiple targets automatically by providing a CSV file.

```bash
python atlas_fp_request.py --file targets.csv
```

**Format of `targets.csv`:**
Create a CSV file with the following headers. The `mjd_max` column is optional and can be left blank to fetch data up to the current date.

```csv
name,ra,dec,mjd_min,mjd_max
SN2023bg,07:42:17.530,-24:22:45.84,59930.0,60050.0
SN2026aip,40.641419677778,-27.350850566667,61050.0
```

### Command-Line Arguments

| Argument | Status | Description | Example |
| :--- | :--- | :--- | :--- |
| `‑‑file` | Optional | Path to a CSV/TXT file containing multiple targets. If provided, overrides all arguments below. | `targets.csv` |
| `‑‑name` | Required* | The name of the astronomical object. | `SN2025wiu` |
| `‑‑ra` | Required* | Right Ascension (HMS or Decimal Degrees). | `01:55:58.487` |
| `‑‑dec` | Required* | Declination (DMS or Decimal Degrees). | `-00:26:43.28` |
| `‑‑mjd_min` | Required* | The minimum MJD to start fetching data. | `60915.0` |
| `‑‑mjd_max` | Optional | The maximum MJD. Leave blank for latest data. | `61073.0` |

*\*Required only if `--file` is not used.*


## Output Files

The pipeline will generate three files in the same directory:
1. `<ObjectName>_LC.txt`: The raw data retrieved directly from ATLAS.
2. `<ObjectName>_binned_LC.txt`: The processed, cleaned, and daily-binned data.
3. `<ObjectName>_LC.png`: The final combined light curve plot (Magnitude and Flux).