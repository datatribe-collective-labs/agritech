"""
Fetches current weather from OpenWeatherMap for all 54 locations.
"""
import sys
import os

# Ensure this scripts folder is on the path regardless of what calls this file
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)



import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from db_utils import get_engine
from shared_locations import GLOBAL_LOCATIONS
from dotenv import load_dotenv
load_dotenv()


# Base URL for OpenWeatherMap API
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Fetch current weather for a single location
def fetch_weather(loc):
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        print("[weather] WARNING: OPENWEATHER_API_KEY not set.")
        return None

    params = {
        "lat":   loc["Lat"],
        "lon":   loc["Lon"],
        "appid": api_key,
        "units": "metric",
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        if response.status_code != 200:
            print(f"[weather] Failed for {loc['City']}: {response.status_code}")
            return None

        data = response.json()
        return {
            "city":                 loc["City"],
            "country":              loc["Country"],
            "latitude":             loc["Lat"],
            "longitude":            loc["Lon"],
            "temperature_c":        data["main"]["temp"],
            "feels_like_c":         data["main"]["feels_like"],
            "min_temp_c":           data["main"]["temp_min"],
            "max_temp_c":           data["main"]["temp_max"],
            "humidity_pct":         data["main"]["humidity"],
            "pressure_hpa":         data["main"]["pressure"],
            "ground_pressure_hpa":  data["main"].get("grnd_level"),
            "wind_speed_mps":       data["wind"]["speed"],
            "wind_direction_deg":   data["wind"]["deg"],
            "cloud_cover_pct":      data["clouds"]["all"],
            "weather_main":         data["weather"][0]["main"],
            "description":          data["weather"][0]["description"],
            "visibility_m":         data.get("visibility"),
        }

    except Exception as e:
        print(f"[weather] Error for {loc['City']}: {e}")
        return None

# Fetch weather for all locations and save to database
def fetch_weather_all():
    print(f"[weather] Fetching for {len(GLOBAL_LOCATIONS)} locations...")

    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(fetch_weather, GLOBAL_LOCATIONS))

    df = pd.DataFrame([r for r in results if r is not None])

    if df.empty:
        print("[weather] No data fetched — check your API_KEY.")
        return

    print(f"[weather] Fetched {len(df)} rows.")
    engine = get_engine()
    df.to_sql("weather", engine, if_exists="append", index=False)
    print(f"[weather] Saved {len(df)} rows to Postgres table 'weather'.")


if __name__ == "__main__":
    fetch_weather_all()
