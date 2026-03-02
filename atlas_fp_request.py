import io
import os
import re
import sys
import time
import argparse
from dotenv import load_dotenv
import pandas as pd
import requests
from astropy.coordinates import SkyCoord
import astropy.units as u
from collections import defaultdict
import math
import numpy as np
from matplotlib import pyplot as plt


parser = argparse.ArgumentParser(description="Download ATLAS force photometry data.")
parser.add_argument('--name', type=str, required=False, help="Object name (e.g., SN2024ggi)")
parser.add_argument('--ra', type=str, required=False, help="Right Ascension (e.g., '11:18:22.087' or '169.592030')")
parser.add_argument('--dec', type=str, required=False, help="Declination (e.g., '-32:50:15.27' or '-32.83757')")
parser.add_argument('--mjd_min', type=float, required=False, help="Minimum MJD")
parser.add_argument('--mjd_max', type=float, required=False, help="Maximum MJD (leave blank to fetch latest)")
parser.add_argument('--file', type=str, required=False, help="Path to CSV/TXT file containing multiple targets")
args = parser.parse_args()

load_dotenv()

username = os.getenv('ATLAS_USERNAME')
password = os.getenv('ATLAS_PASSWORD')

if not username or not password:
    print("Error: Please set ATLAS_USERNAME and ATLAS_PASSWORD via .env file")
    sys.exit(1)

# Determine coordinate format
def get_coord_format(ra, dec):
    try:
        if any(char in str(ra) for char in [':', ' ']):
            c = SkyCoord(ra=ra, dec=dec, unit=(u.hourangle, u.deg))
            fmt = "Sexagesimal (HMS/DMS)"
        else:
            c = SkyCoord(ra=ra, dec=dec, unit=(u.deg, u.deg))
            fmt = "Decimal (Degrees)"
        
        return c, fmt
    except Exception as e:
        return None, f"Error: {e}"
        
if args.file:
    targets_df = pd.read_csv(args.file)
    if 'mjd_max' not in targets_df.columns:
        targets_df['mjd_max'] = None
else:
    if not args.name or not args.ra or not args.dec or not args.mjd_min:
        print("Error: You must provide either --file OR --name, --ra, --dec, and --mjd_min.")
        sys.exit(1)
    targets_df = pd.DataFrame([{
        'name': args.name, 'ra': args.ra, 'dec': args.dec, 
        'mjd_min': args.mjd_min, 'mjd_max': args.mjd_max
    }])

user_choice = input(f"\nFound {len(targets_df)} target(s). Do you want to auto-bin and plot them all? (y/n): ").strip().lower()
process_and_plot = user_choice in ['y', 'yes']

for index, row in targets_df.iterrows():
    obj_name = str(row['name'])
    ra_input = str(row['ra'])
    dec_input = str(row['dec'])
    MJD_min = float(row['mjd_min'])
    MJD_max = float(row['mjd_max']) if pd.notna(row['mjd_max']) else None
    
    print(f"[{index+1}/{len(targets_df)}] Processing target: {obj_name}")

    script_directory = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_directory, obj_name)
    os.makedirs(target_dir, exist_ok=True)

    #-----------------------------------------------------------------------------------------------------
    ### 1. To get ATLAS forced photometry data for a specific object and save the raw data to a text file.
    #-----------------------------------------------------------------------------------------------------

    coord, coord_type = get_coord_format(ra_input, dec_input)
    ra = coord.ra.deg
    dec = coord.dec.deg


    # Request
    BASEURL = "https://fallingstar-data.com/forcedphot"

    resp = requests.post(url=f"{BASEURL}/api-token-auth/", data={'username': username, 'password': password})

    if resp.status_code == 200:
        token = resp.json()['token']
        print(f'Your token is {token}')
        headers = {'Authorization': f'Token {token}', 'Accept': 'application/json'}
    else:
        print(f'ERROR {resp.status_code}')
        print(resp.json())

    task_url = None
    while not task_url:
        with requests.Session() as s:
            resp = s.post(f"{BASEURL}/queue/", headers=headers, data={
                'ra': ra, 'dec': dec, 'mjd_min': MJD_min, 'mjd_max': MJD_max})

            if resp.status_code == 201:  # successfully queued
                task_url = resp.json()['url']
                print(f'The task URL is {task_url}')
            elif resp.status_code == 429:  # throttled
                message = resp.json()["detail"]
                print(f'{resp.status_code} {message}')
                t_sec = re.findall(r'available in (\d+) seconds', message)
                t_min = re.findall(r'available in (\d+) minutes', message)
                if t_sec:
                    waittime = int(t_sec[0])
                elif t_min:
                    waittime = int(t_min[0]) * 60
                else:
                    waittime = 10
                print(f'Waiting {waittime} seconds')
                time.sleep(waittime)
            else:
                print(f'ERROR {resp.status_code}')
                print(resp.json())
                continue

    result_url = None
    while not result_url:
        with requests.Session() as s:
            resp = s.get(task_url, headers=headers)

            if resp.status_code == 200:  # HTTP OK
                if resp.json()['finishtimestamp']:
                    result_url = resp.json()['result_url']
                    print(f"Task is complete with results available at {result_url}")
                    break
                elif resp.json()['starttimestamp']:
                    print(f"Task is running (started at {resp.json()['starttimestamp']})")
                else:
                    print("Waiting for job to start. Checking again in 10 seconds...")
                time.sleep(10)
            else:
                print(f'ERROR {resp.status_code}')
                print(resp.json())
                continue

    with requests.Session() as s:
        textdata = s.get(result_url, headers=headers).text

    dfresult = pd.read_csv(io.StringIO(textdata.replace("###", "")), delim_whitespace=True)
    print(dfresult)

    LC_name = f'{obj_name}_LC.txt'
    LC_file = os.path.join(target_dir, f'{obj_name}_LC.txt')
    with open(LC_file, 'w') as file:
        file.write(textdata)
    print(f"Raw data has been saved to '{obj_name}_LC.txt'")

    with requests.Session() as s:
        delete_response = s.delete(task_url, headers=headers)
        print(delete_response.text)



    #-------------------------------------------------------------------------------
    ### 2. Processing the raw ATLAS light curve data (both before and after binning)
    #-------------------------------------------------------------------------------

    if process_and_plot:
        print(f"\nStarting daily binning for {obj_name}...")
        
        daily_bins = defaultdict(lambda: {'sum_w_ujy': 0.0, 'sum_w_mjd': 0.0, 'sum_w': 0.0, 'count': 0})
        
        valid_data = []
        with open(LC_file, 'r') as f_in:
            header_line = f_in.readline().strip().replace('###', '')
            header_cols = header_line.split()
            try: chi_n_idx = header_cols.index('chi/N')
            except ValueError: chi_n_idx = None

            for line in f_in:
                parts = line.split()
                if len(parts) < 6: continue
                try:
                    mjd, m, dm, ujy, dujy, filt = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), parts[5]
                    chi_n = float(parts[chi_n_idx]) if chi_n_idx and len(parts) > chi_n_idx else 0.0
                except ValueError:
                    continue
                
                if dujy <= 0 or dujy > 4000 or (chi_n_idx and chi_n > 100):
                    continue
                
                valid_data.append({'MJD': mjd, 'uJy': ujy, 'duJy': dujy, 'F': filt})

        df_raw = pd.DataFrame(valid_data)
        clipped_data = []
        window_size = 11      
        sigma_clip_level = 3.0 

        if not df_raw.empty:
            for filt in df_raw['F'].unique():
                df_f = df_raw[df_raw['F'] == filt].sort_values('MJD').copy()

                rolling_median = df_f['uJy'].rolling(window=window_size, center=True, min_periods=3).median()
                rolling_std = df_f['uJy'].rolling(window=window_size, center=True, min_periods=3).std()

                rolling_median = rolling_median.fillna(df_f['uJy'].median())
                rolling_std = rolling_std.fillna(df_f['uJy'].std())

                outlier_mask = np.abs(df_f['uJy'] - rolling_median) > (sigma_clip_level * rolling_std)

                df_f_clean = df_f[~outlier_mask]
                
                outliers_count = outlier_mask.sum()
                
                clipped_data.append(df_f_clean)

            df_clean = pd.concat(clipped_data)
        else:
            df_clean = df_raw

        daily_bins = defaultdict(lambda: {'sum_w_ujy': 0.0, 'sum_w_mjd': 0.0, 'sum_w': 0.0, 'count': 0})
        
        for _, row in df_clean.iterrows():
            mjd, ujy, dujy, filt = row['MJD'], row['uJy'], row['duJy'], row['F']
            w = 1.0 / (dujy ** 2)
            day_int = int(mjd)
            key = (day_int, filt)
            
            daily_bins[key]['sum_w_ujy'] += ujy * w     
            daily_bins[key]['sum_w_mjd'] += mjd * w     
            daily_bins[key]['sum_w'] += w               
            daily_bins[key]['count'] += 1

        processed_lines_after_bin = []
        sorted_keys = sorted(daily_bins.keys())
        ZP = 23.9
        processed_lines_after_bin.append("#MJD       Mag     dMag    uJy      duJy    F   N\n")

        for key in sorted_keys:
            data = daily_bins[key]
            filt = f'ATLAS-{key[1]}'
            sum_w = data['sum_w']
            if sum_w == 0: continue

            mean_mjd = data['sum_w_mjd'] / sum_w
            mean_ujy = data['sum_w_ujy'] / sum_w
            mean_dujy = 1.0 / math.sqrt(sum_w)
            count = data['count']
            
            if mean_ujy > 0:
                mean_m = -2.5 * math.log10(mean_ujy) + ZP
                mean_dm = 1.0857 * (mean_dujy / mean_ujy)
            else:
                mean_m, mean_dm = -99.99, -99.99
            
            processed_lines_after_bin.append(f"{mean_mjd:.5f} {mean_m:.4f} {mean_dm:.4f} {mean_ujy:.4f} {mean_dujy:.4f} {filt} {count}\n")

        data_output_after_bin = os.path.join(target_dir, f'{obj_name}_binned_LC.txt')
        with open(data_output_after_bin, 'w') as f_out:
            f_out.writelines(processed_lines_after_bin)

        print(f"Binning complete! Saved to {data_output_after_bin}")

        print("Start to plot Light Curve...")
        df = pd.read_csv(data_output_after_bin, sep='\s+', header=None,
                        names=['MJD', 'mag', 'mag_err', 'flux', 'flux_err', 'band', 'count'], skiprows=1)
        min_mag = df[df['mag'] > 0]['mag'].min()
        limit_val = min_mag - (25 - min_mag) / 4
        band_colors = {'ATLAS-c': '#1f77b4', 'ATLAS-o': '#ff7f0e'}
        band_markers = {'ATLAS-c': 'o', 'ATLAS-o': 's'}
        bands = df['band'].unique()

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [1, 1], 'hspace': 0.05})

        # Magnitude
        for band in bands:
            df_band = df[df['band'] == band]
            valid_df = df_band[df_band['mag'] > 0]
            if valid_df.empty: continue
            valid_mags = df[df['mag'] > 0]['mag']
            min_mag = valid_mags.min()
            max_mag = valid_mags.max()
            mag_range = max_mag - min_mag
            ax1.errorbar(valid_df['MJD'], valid_df['mag'], yerr=valid_df['mag_err'], fmt='none', color=band_colors.get(band, 'k'), alpha=0.6, capsize=3, zorder=1)
            ax1.scatter(valid_df['MJD'], valid_df['mag'], color=band_colors.get(band, 'k'), marker=band_markers.get(band, 'o'), s=50, label=f'{band}', zorder=2)

        ax1.set_ylabel('Apparent Magnitude (AB)', fontsize=14)
        plot_top = min_mag - (0.15 * mag_range)
        plot_bottom = max_mag + (0.10 * mag_range)
        ax1.set_ylim(top=plot_top, bottom=plot_bottom)
        ax1.grid(True, linestyle=':', alpha=0.7)
        ax1.legend(loc='best', fontsize=12)
        ax1.tick_params(axis='both', which='major', labelsize=12)

        # Flux
        for band in bands:
            df_band = df[df['band'] == band]
            ax2.errorbar(df_band['MJD'], df_band['flux'], yerr=df_band['flux_err'], fmt='none', color=band_colors.get(band, 'k'), alpha=0.6, capsize=3, zorder=1)
            ax2.scatter(df_band['MJD'], df_band['flux'], color=band_colors.get(band, 'k'), marker=band_markers.get(band, 'o'), s=50, label=f'{band}', zorder=2)

        ax2.axhline(0, color='gray', linestyle='--', linewidth=1.5, alpha=0.5)
        ax2.set_xlabel('Modified Julian Date (MJD)', fontsize=14)
        ax2.set_ylabel('Flux ($\mu$Jy)', fontsize=14) 
        ax2.grid(True, linestyle=':', alpha=0.7)
        ax2.tick_params(axis='both', which='major', labelsize=12)

        fig.suptitle(f'{obj_name} ATLAS Light Curve', fontsize=16, fontweight='bold', y=0.92)
        plt.subplots_adjust(top=0.88, bottom=0.1, left=0.1, right=0.95)

        output_file = os.path.join(target_dir, f'{obj_name}_LC_plot.png')
        plt.savefig(output_file, dpi=600)
        plt.close(fig)

        print(f"Plotting complete! Figure saved to {output_file}")

    else:
        print(f"\nSkipping binning and plotting. Program finished.")