"""
Fetches REAL, field-measured soil data from WoSIS (World Soil
"""

import sys
import time
import math
import logging
from datetime import datetime
from pathlib import Path

import requests
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from db_utils import get_engine
from scripts.shared_locations import GLOBAL_LOCATIONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

## WoSIS API details
WOSIS_URL = "https://graphql.isric.org/wosis/graphql"

# Look for nearby profiles within ~55km (0.5deg) first. If any property is still missing,
# widen to a ring of eight neighbouring 1-degree tiles around the city (reaching ~165km).
# Tiles are used instead of one large box because WoSIS returns at most 20 profiles per query:
# in a data-rich area one large box returns an arbitrary 20 and can miss the profiles that have a pH reading.
NEAR_BOX_DEG = 0.5
TILE_HALF_WIDTH_DEG = 0.5
TILE_OFFSETS_DEG = (-1.0, 0.0, 1.0)
WIDE_REACH_DEG = max(TILE_OFFSETS_DEG) + TILE_HALF_WIDTH_DEG

# WoSIS API limits the number of profiles returned per query to 20, and the number of layers per profile to 3.
MAX_PROFILES_PER_QUERY = 20  
MAX_LAYERS_PER_PROFILE = 3    

# GraphQL query to retrieve soil data to avoid rewriting query for each location.
QUERY_TEMPLATE = """
{{
  wosisLatestProfiles(
    filter: {{
      latitude: {{ greaterThanOrEqualTo: {lat_min}, lessThanOrEqualTo: {lat_max} }}
      longitude: {{ greaterThanOrEqualTo: {lon_min}, lessThanOrEqualTo: {lon_max} }}
    }}
    first: {max_profiles}
  ) {{
    profileId
    latitude
    longitude
    countryName
    year
    layers(first: {max_layers}) {{
      upperDepth
      lowerDepth
      phaqValues(first: 1)   {{ value valueAvg }}
      clayValues(first: 1)   {{ value }}
      sandValues(first: 1)   {{ value }}
      siltValues(first: 1)   {{ value }}
      orgcValues(first: 1)   {{ value }}
      nitkjdValues(first: 1) {{ value }}
    }}
  }}
}}
"""

# Calculates the shortest distance in kilometres between two locations using their latitude and longitude.
# The Haversine formula accounts for the Earth's curvature, making the distance much more accurate than simple Euclidean distance.
# This to determine how far each soil profile is from the target city so that closer profiles can have a greater influence in the weighted average
def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    # Earth average radius in km
    R = 6371.0
    # Convert degrees to radians for the latitude and longitude values
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    # Calculate the spherical distance using the Haversine formula
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    # Return the distance in kilometers
    return 2 * R * math.asin(math.sqrt(a))

# Extracts the average value of a soil property from the WoSIS API response.
def extract_value(value_list):
    """
    WoSIS returns e.g. [{"value": ["6.6"], "valueAvg": 6.6}] for a
    real measurement, or [] if this profile/layer has no observation
    for this property.
    """
    if not value_list:
        return None
    entry = value_list[0]
    if entry.get("valueAvg") is not None:
        return float(entry["valueAvg"])
    raw = entry.get("value")
    if raw:
        try:
            return float(raw[0])
        except (ValueError, TypeError, IndexError):
            return None
    return None

# Fetch soil data for a specific city by querying the WoSIS API with progressively 
# larger bounding.
def shallowest_layer(layers):
    """
    Picks the layer with minimum upperDepth..
    """
    if not layers:
        return None
    return min(layers, key=lambda l: l["upperDepth"])

# Calculate the inverse-distance weighted average of a specific soil property 
# across all found profiles.
def distance_weighted_average(profiles, city_lat, city_lon, property_key):
    """
    Inverse-distance weighted average of one property across all
    profiles found, using each profile's shallowest layer only, and
    Skips profiles missing this specific property (partial-data
    tolerant) rather than dropping the whole profile.
    """
    weighted_sum = 0.0
    weight_total = 0.0
    used = 0
    for p in profiles:
        layer = shallowest_layer(p["layers"])
        if layer is None:
            continue
        val = extract_value(layer.get(property_key, []))
        if val is None:
            continue
        dist = haversine_km(city_lat, city_lon, p["latitude"], p["longitude"])
        weight = 1.0 / (dist + 0.1)  # +0.1km epsilon guards divide-by-zero
        weighted_sum += val * weight
        weight_total += weight
        used += 1
    if weight_total == 0:
        return None, 0
    return round(weighted_sum / weight_total, 2), used

# Find soil profiles within a bounding box.
def query_wosis_box(lat, lon, box_deg):
    """Runs one bounding-box query against the WoSIS API."""
    query = QUERY_TEMPLATE.format(
        lat_min=lat - box_deg, lat_max=lat + box_deg,
        lon_min=lon - box_deg, lon_max=lon + box_deg,
        max_profiles=MAX_PROFILES_PER_QUERY,
        max_layers=MAX_LAYERS_PER_PROFILE,
    )
    response = requests.post(WOSIS_URL, json={"query": query}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        raise RuntimeError(f"WoSIS GraphQL errors: {data['errors']}")
    return data["data"]["wosisLatestProfiles"]

# Soil columns we store: column name -> (WoSIS field, factor used to store it as a whole number)
SOIL_PROPERTIES = {
    "phh2o_0_5cm":    ("phaqValues",   10),
    "clay_0_5cm":     ("clayValues",   10),
    "sand_0_5cm":     ("sandValues",   10),
    "silt_0_5cm":     ("siltValues",   10),
    "soc_0_5cm":      ("orgcValues",   10),
    "nitrogen_0_5cm": ("nitkjdValues", 100),
}


def missing_properties(profiles, lat, lon):
    """Names of the soil properties that no profile in this list has a measurement for."""
    return [
        column for column, (field, _) in SOIL_PROPERTIES.items()
        if distance_weighted_average(profiles, lat, lon, field)[1] == 0
    ]


def fetch_wide_area(lat, lon):
    """
    Profiles from the 3 x 3 grid of 1-degree tiles centred on the city, without duplicates.
    A tile that comes back full (20 profiles) may have more profiles than were returned.
    """
    found = {}
    for dy in TILE_OFFSETS_DEG:
        for dx in TILE_OFFSETS_DEG:
            tile = query_wosis_box(lat + dy, lon + dx, TILE_HALF_WIDTH_DEG)
            if len(tile) >= MAX_PROFILES_PER_QUERY:
                logger.info(f"  Tile ({dy:+.0f}, {dx:+.0f}) is full - more profiles may exist than were returned")
            for p in tile:
                found[p["profileId"]] = p
    return list(found.values())


# Fetch soil data for a specific city
def fetch_soil_for_city(city_name, lat, lon):
    """
    Returns a list of (reach_degrees, profiles), nearest search first.

    The wider search runs when the near box has no profiles OR when some property (for example pH)
    has no measurement in it. Widening only for "no profiles" left pH empty for cities where
    nearby profiles existed but none had a pH reading.
    """
    levels = []
    near = query_wosis_box(lat, lon, NEAR_BOX_DEG)
    if near:
        levels.append((NEAR_BOX_DEG, near))
        if not missing_properties(near, lat, lon):
            return levels
    logger.info(f"  Not enough data within {NEAR_BOX_DEG}deg - searching the surrounding tiles")
    wide = fetch_wide_area(lat, lon)
    if wide:
        levels.append((WIDE_REACH_DEG, wide))
    return levels


# Build a row of soil data for a city
def build_soil_row(city, country, lat, lon, levels):
    """
    For each soil property, takes the distance-weighted average from the smallest search box
    that has a measurement for it (shallowest layer of each profile only).
    A property with no measurement in any box stays empty.
    """
    row = {
        "city": city, "country": country, "latitude": lat, "longitude": lon,
        "soil_data_source": "wosis", "ingested_at": datetime.utcnow(),
    }
    n_used = {}
    for column, (field, factor) in SOIL_PROPERTIES.items():
        row[column], n_used[column] = None, 0
        for _, profiles in levels:
            value, n = distance_weighted_average(profiles, lat, lon, field)
            if value is not None:
                row[column], n_used[column] = round(value * factor), n
                break
    row["wosis_profiles_used"] = len(levels[0][1]) if levels else 0
    row["wosis_box_degrees_used"] = levels[-1][0] if levels else None
    row["wosis_ph_n_profiles"] = n_used["phh2o_0_5cm"]
    return row


# Fetch soil data for all 54 cities from WoSIS and writes to public.soil. 
def fetch_soil():
    # Connect to the data base
    engine    = get_engine()
    succeeded = 0
    no_coverage = []
    failed    = []

    logger.info(f"[soil] Fetching {len(GLOBAL_LOCATIONS)} cities from WoSIS")
    logger.info("=" * 50)

    for i, loc in enumerate(GLOBAL_LOCATIONS, 1):
        city_name = loc["City"]
        lat, lon  = loc["Lat"], loc["Lon"]
        logger.info(f"[{i:2d}/{len(GLOBAL_LOCATIONS)}] {city_name}")

        try:
            levels = fetch_soil_for_city(city_name, lat, lon)

            if not levels:
                logger.info(f"  No WoSIS coverage found for {city_name} — leaving NULL")
                no_coverage.append(city_name)
                row = build_soil_row(city_name, loc["Country"], lat, lon, [])
                df = pd.DataFrame([row])
                df.to_sql("soil", engine, schema="public", if_exists="append", index=False)
                continue

            row = build_soil_row(city_name, loc["Country"], lat, lon, levels)
            df = pd.DataFrame([row])
            df.to_sql("soil", engine, schema="public", if_exists="append", index=False)

            ph_display = row["phh2o_0_5cm"] / 10 if row["phh2o_0_5cm"] else "null"
            logger.info(
                f"  Saved | pH: {ph_display} | {row['wosis_profiles_used']} profiles "
                f"in the closest box, widest box {row['wosis_box_degrees_used']}deg | source: wosis"
            )
            succeeded += 1

        except Exception as e:
            logger.warning(f"  Failed: {e}")
            failed.append(city_name)

        time.sleep(0.3)  # light courtesy delay, WoSIS has no documented rate limit

    logger.info("\n" + "=" * 50)
    logger.info(f"  Succeeded:     {succeeded}/{len(GLOBAL_LOCATIONS)}")
    if no_coverage:
        logger.info(f"  No coverage:   {len(no_coverage)} — {', '.join(no_coverage)}")
    if failed:
        logger.info(f"  Failed (error): {', '.join(failed)}")
    logger.info("=" * 50)


if __name__ == "__main__":
    fetch_soil()
