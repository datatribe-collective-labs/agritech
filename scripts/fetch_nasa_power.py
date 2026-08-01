"""
Fetches 10 years of daily historical climate data from NASA POWER API.

Each location × 10 years × 365 days = ~3,650 rows per city.
Across 54 cities = ~197,000 rows total.

Parameters fetched:
  T2M          - Temperature at 2m height (°C)
  T2M_MAX      - Max daily temperature (°C)
  T2M_MIN      - Min daily temperature (°C)
  PRECTOTCORR  - Precipitation corrected (mm/day)
  RH2M         - Relative humidity at 2m (%)
  WS2M         - Wind speed at 2m (m/s)
  ALLSKY_SFC_SW_DWN - Solar radiation (MJ/m²/day) — key for photosynthesis
  GWETROOT     - Root zone soil wetness (0-1)
"""
import sys
import os

# Ensure this scripts folder is on the path regardless of what calls this file
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if not SCRIPTS_DIR:
    SCRIPTS_DIR = "/opt/airflow/scripts"
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
# Always also insert the hardcoded path as a fallback
if "/opt/airflow/scripts" not in sys.path:
    sys.path.insert(0, "/opt/airflow/scripts")



import requests
import pandas as pd
import time
from sqlalchemy import text
from db_utils import get_engine
from shared_locations import GLOBAL_LOCATIONS

NASA_URL   = "https://power.larc.nasa.gov/api/temporal/daily/point"
START_YEAR = "20150101"   # 10 years of history
END_YEAR   = "20241231"

PARAMETERS = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "RH2M",
    "WS2M",
    "ALLSKY_SFC_SW_DWN",
    "GWETROOT",
]


def fetch_nasa_location(loc):
    """
    Fetches 10 years of daily historical climate data from NASA POWER API
    for a single location and returns a list of dicts (rows).
    """
    city = loc["City"]
    lat  = loc["Lat"]
    lon  = loc["Lon"]

    params = {
        "parameters": ",".join(PARAMETERS),
        "community":  "AG",          # Agriculture community
        "longitude":  lon,
        "latitude":   lat,
        "start":      START_YEAR,
        "end":        END_YEAR,
        "format":     "JSON",
    }

    try:
        resp = requests.get(NASA_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # NASA returns data as {PARAM: {YYYYMMDD: value, ...}, ...}
        properties = data.get("properties", {}).get("parameter", {})

        if not properties:
            print(f"[nasa] No data for {city}")
            return []

        # Get all dates from first parameter
        dates = list(next(iter(properties.values())).keys())

        rows = []
        for date_str in dates:
            row = {
                "city":      city,
                "country":   loc["Country"],
                "latitude":  lat,
                "longitude": lon,
                "date":      f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            }
            for param in PARAMETERS:
                value = properties.get(param, {}).get(date_str)
                # NASA uses -999 as null
                row[param.lower()] = None if value == -999 else value

            rows.append(row)

        print(f"[nasa] {city}: {len(rows)} daily records")
        return rows

    except Exception as e:
        print(f"[nasa] Failed for {city}: {e}")
        return []

def fetch_nasa_power():
    """
    Fetches 10 years of daily historical climate data from NASA POWER API
    for all locations in GLOBAL_LOCATIONS and saves to the database.
    """
    print(f"[nasa] Fetching 10yr history for {len(GLOBAL_LOCATIONS)} locations...")
    print(f"[nasa] This may take 5-10 minutes — NASA rate-limits requests.")

    all_rows = []

    for i, loc in enumerate(GLOBAL_LOCATIONS):
        rows = fetch_nasa_location(loc)
        all_rows.extend(rows)

        # NASA recommends a small delay between requests
        time.sleep(0.5)

        # Save in batches of 10 cities to avoid memory issues
        if (i + 1) % 10 == 0:
            print(f"[nasa] Progress: {i+1}/{len(GLOBAL_LOCATIONS)} cities, {len(all_rows)} rows so far")
            _save_batch(all_rows)
            all_rows = []

    # Save any remaining rows
    if all_rows:
        _save_batch(all_rows)

    print("[nasa] Done.")


def _save_batch(rows):
    """
    Upserts a batch via a temp staging table + INSERT ... ON CONFLICT
    DO NOTHING, instead of blind append.
    """
    if not rows:
        return
    df = pd.DataFrame(rows)
    engine = get_engine()

    with engine.begin() as conn:
        df.to_sql(
            "nasa_climate_staging_tmp", conn,
            if_exists="replace", index=False,
        )
        result = conn.execute(text("""
            INSERT INTO public.nasa_climate
            SELECT * FROM public.nasa_climate_staging_tmp
            ON CONFLICT (city, date) DO NOTHING
        """))
        conn.execute(text("DROP TABLE public.nasa_climate_staging_tmp"))

    print(f"[nasa] Processed batch of {len(df)} rows (duplicates skipped via ON CONFLICT).")


if __name__ == "__main__":
    fetch_nasa_power()
