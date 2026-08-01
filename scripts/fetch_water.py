"""
Fetches precipitation, Evapotranspiration, and river discharge
from Open-Meteo for all global locations.
"""
import sys
import os

# Ensure this scripts folder is on the path regardless of what calls this file
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


# Import dependencies
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from db_utils import get_engine
from shared_locations import GLOBAL_LOCATIONS

# URLs for Open-Meteo APIs
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL   = "https://flood-api.open-meteo.com/v1/flood"

# Fetch average daily precipitation and ET0 for a location
def fetch_precip_et(loc):
    city = loc["City"]
    lat  = loc["Lat"]
    lon  = loc["Lon"]

    params = {
        "latitude":      lat,
        "longitude":     lon,
        "daily":         ["precipitation_sum", "et0_fao_evapotranspiration"],
        "forecast_days": 7,
        "timezone":      "auto",
    }

    try:
        resp = requests.get(WEATHER_URL, params=params, timeout=15)
        resp.raise_for_status()
        data        = resp.json()
        daily       = data.get("daily", {})
        precip_vals = daily.get("precipitation_sum", [])
        et0_vals    = daily.get("et0_fao_evapotranspiration", [])
        dates       = daily.get("time", [])

        avg_precip = round(sum(v for v in precip_vals if v) / len(precip_vals), 2) if precip_vals else None
        avg_et0    = round(sum(v for v in et0_vals    if v) / len(et0_vals),    2) if et0_vals    else None
        deficit    = round(avg_et0 - avg_precip, 2) if avg_et0 and avg_precip else None

        return {
            "city":                      city,
            "country":                   loc["Country"],
            "latitude":                  lat,
            "longitude":                 lon,
            "avg_daily_precip_mm":       avg_precip,
            "avg_daily_et0_mm":          avg_et0,
            "avg_daily_water_deficit_mm":deficit,
            "forecast_start_date":       dates[0]  if dates else None,
            "forecast_end_date":         dates[-1] if dates else None,
        }

    except Exception as e:
        print(f"[water/precip] Failed for {city}: {e}")
        return None

# Fetch average daily river discharge for a location
def fetch_river_discharge(loc):
    city   = loc["City"]
    params = {
        "latitude":      loc["Lat"],
        "longitude":     loc["Lon"],
        "daily":         "river_discharge",
        "forecast_days": 16,
    }
    try:
        resp = requests.get(FLOOD_URL, params=params, timeout=15)
        resp.raise_for_status()
        vals = resp.json().get("daily", {}).get("river_discharge", [])
        return {
            "city":                    city,
            "avg_river_discharge_m3s": round(sum(v for v in vals if v) / len(vals), 2) if vals else None,
            "max_river_discharge_m3s": round(max((v for v in vals if v), default=0), 2),
        }
    except Exception as e:
        print(f"[water/river] Failed for {city}: {e}")
        return {"city": city, "avg_river_discharge_m3s": None, "max_river_discharge_m3s": None}

# Fetch water data for all locations
def fetch_water():
    print(f"[water] Fetching for {len(GLOBAL_LOCATIONS)} locations...")

    # Fetch precipitation and Evapotranspiration in parallel for all locations
    with ThreadPoolExecutor(max_workers=10) as ex:
        precip_results = list(ex.map(fetch_precip_et,       GLOBAL_LOCATIONS))

    with ThreadPoolExecutor(max_workers=10) as ex:
        river_results  = list(ex.map(fetch_river_discharge, GLOBAL_LOCATIONS))

    # Merge results into a single DataFrame and save to database
    precip_df = pd.DataFrame([r for r in precip_results if r is not None])
    river_df  = pd.DataFrame([r for r in river_results  if r is not None])
    df = precip_df.merge(river_df, on="city", how="left")

    print(f"[water] Fetched {len(df)} rows.")#
    engine = get_engine()
    df.to_sql("water", engine, if_exists="append", index=False)
    print(f"[water] Saved {len(df)} rows to Postgres table 'water'.")


if __name__ == "__main__":
    fetch_water()
