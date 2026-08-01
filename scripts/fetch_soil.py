# """
# Fetches REAL, field-measured soil data from WoSIS (World Soil
# """

# import profile
# import sys
# import time
# import math
# import logging
# from datetime import datetime
# from pathlib import Path

# import requests
# import pandas as pd

# sys.path.insert(0, str(Path(__file__).parent.parent))
# from db_utils import get_engine
# from scripts.shared_locations import GLOBAL_LOCATIONS

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# ## WoSIS API details
# WOSIS_URL = "https://graphql.isric.org/wosis/graphql"

# # Look for nearby profiles within ~55km (0.5deg) first, then widen to ~220km (2.0deg)
# # Without it, many cities with no nearby profiles would return no soil data, even though usable profiles exist slightly farther away.
# BOX_SIZES_DEG = [0.5, 2.0]

# # WoSIS API limits the number of profiles returned per query to 20, and the number of layers per profile to 3.
# MAX_PROFILES_PER_QUERY = 20  
# MAX_LAYERS_PER_PROFILE = 3    

# # GraphQL query to retrieve soil data to avoid rewriting query for each location.
# QUERY_TEMPLATE = """
# {{
#   wosisLatestProfiles(
#     filter: {{
#       latitude: {{ greaterThanOrEqualTo: {lat_min}, lessThanOrEqualTo: {lat_max} }}
#       longitude: {{ greaterThanOrEqualTo: {lon_min}, lessThanOrEqualTo: {lon_max} }}
#     }}
#     first: {max_profiles}
#   ) {{
#     profileId
#     latitude
#     longitude
#     countryName
#     year
#     layers(first: {max_layers}) {{
#       upperDepth
#       lowerDepth
#       phaqValues(first: 1)   {{ value valueAvg }}
#       clayValues(first: 1)   {{ value }}
#       sandValues(first: 1)   {{ value }}
#       siltValues(first: 1)   {{ value }}
#       orgcValues(first: 1)   {{ value }}
#       nitkjdValues(first: 1) {{ value }}
#     }}
#   }}
# }}
# """

# # Calculates the shortest distance in kilometres between two locations using their latitude and longitude.
# # The Haversine formula accounts for the Earth's curvature, making the distance much more accurate than simple Euclidean distance.
# # This to determine how far each soil profile is from the target city so that closer profiles can have a greater influence in the weighted average
# def haversine_km(lat1, lon1, lat2, lon2):
#     """Great-circle distance in km between two lat/lon points."""
#     # Earth average radius in km
#     R = 6371.0
#     # Convert degrees to radians for the latitude and longitude values
#     phi1, phi2 = math.radians(lat1), math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lon2 - lon1)
#     # Calculate the spherical distance using the Haversine formula
#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     # Return the distance in kilometers
#     return 2 * R * math.asin(math.sqrt(a))

# # Extracts the average value of a soil property from the WoSIS API response.
# def extract_value(value_list):
#     """
#     WoSIS returns e.g. [{"value": ["6.6"], "valueAvg": 6.6}] for a
#     real measurement, or [] if this profile/layer has no observation
#     for this property.
#     """
#     if not value_list:
#         return None
#     entry = value_list[0]
#     if entry.get("valueAvg") is not None:
#         return float(entry["valueAvg"])
#     raw = entry.get("value")
#     if raw:
#         try:
#             return float(raw[0])
#         except (ValueError, TypeError, IndexError):
#             return None
#     return None

# # Fetch soil data for a specific city by querying the WoSIS API with progressively 
# # larger bounding.
# def shallowest_layer(layers):
#     """
#     Picks the layer with minimum upperDepth..
#     """
#     if not layers:
#         return None
#     return min(layers, key=lambda l: l["upperDepth"])

# # Calculate the inverse-distance weighted average of a specific soil property 
# # across all found profiles.
# def distance_weighted_average(profiles, city_lat, city_lon, property_key):
#     """
#     Inverse-distance weighted average of one property across all
#     profiles found, using each profile's shallowest layer only, and
#     Skips profiles missing this specific property (partial-data
#     tolerant) rather than dropping the whole profile.
#     """
#     weighted_sum = 0.0
#     weight_total = 0.0
#     used = 0
#     for p in profiles:
#         layer = shallowest_layer(p["layers"])
#         if layer is None:
#             continue
#         val = extract_value(layer.get(property_key, []))
#         if val is None:
#             continue
#         dist = haversine_km(city_lat, city_lon, p["latitude"], p["longitude"])
#         weight = 1.0 / (dist + 0.1)  # +0.1km epsilon guards divide-by-zero
#         weighted_sum += val * weight
#         weight_total += weight
#         used += 1
#     if weight_total == 0:
#         return None, 0
#     return round(weighted_sum / weight_total, 2), used

# # Find soil profiles within a bounding box.
# def query_wosis_box(lat, lon, box_deg):
#     """Runs one bounding-box query against the WoSIS API."""
#     query = QUERY_TEMPLATE.format(
#         lat_min=lat - box_deg, lat_max=lat + box_deg,
#         lon_min=lon - box_deg, lon_max=lon + box_deg,
#         max_profiles=MAX_PROFILES_PER_QUERY,
#         max_layers=MAX_LAYERS_PER_PROFILE,
#     )
#     response = requests.post(WOSIS_URL, json={"query": query}, timeout=30)
#     response.raise_for_status()
#     data = response.json()
#     if "errors" in data:
#         raise RuntimeError(f"WoSIS GraphQL errors: {data['errors']}")
#     return data["data"]["wosisLatestProfiles"]

# # Fetch soil data for a specific city
# def fetch_soil_for_city(city_name, lat, lon):
#     """
#     Returns (profiles, box_size_used)box_size_used is None if genuinely no coverage 
#     was found at any tested radius.
#     """
#     for box_deg in BOX_SIZES_DEG:
#         profiles = query_wosis_box(lat, lon, box_deg)
#         if profiles:
#             return profiles, box_deg
#         logger.info(f"  No profiles within {box_deg}deg — widening")
#     return [], None

# # Build a row of soil data for a city
# def build_soil_row(city, country, lat, lon, profiles, box_deg_used):
#     # Computes the distance-weighted average of each soil property across all found 
#     # profiles, using only the shallowest layer of each profile. 
#     # Returns a dictionary representing a row of soil data for the city.
#     ph, n_ph     = distance_weighted_average(profiles, lat, lon, "phaqValues")
#     clay, n_clay = distance_weighted_average(profiles, lat, lon, "clayValues")
#     sand, n_sand = distance_weighted_average(profiles, lat, lon, "sandValues")
#     silt, n_silt = distance_weighted_average(profiles, lat, lon, "siltValues")
#     orgc, n_orgc = distance_weighted_average(profiles, lat, lon, "orgcValues")
#     nitkjd, n_n  = distance_weighted_average(profiles, lat, lon, "nitkjdValues")

#     return {
#         "city":              city,
#         "country":           country,
#         "latitude":          lat,
#         "longitude":         lon,
#         "soil_data_source":  "wosis",
#         "ingested_at":       datetime.utcnow(),
#         "phh2o_0_5cm":       round(ph * 10) if ph is not None else None,
#         "clay_0_5cm":        round(clay * 10) if clay is not None else None,
#         "sand_0_5cm":        round(sand * 10) if sand is not None else None,
#         "silt_0_5cm":        round(silt * 10) if silt is not None else None,
#         "soc_0_5cm":         round(orgc * 10) if orgc is not None else None,
#         "nitrogen_0_5cm":    round(nitkjd * 100) if nitkjd is not None else None,
#         "wosis_profiles_used":     len(profiles),
#         "wosis_box_degrees_used":  box_deg_used,
#         "wosis_ph_n_profiles":     n_ph,
#     }

# # Fetch soil data for all 54 cities from WoSIS and writes to public.soil. 
# def fetch_soil():
#     # Connect to the data base
#     engine    = get_engine()
#     succeeded = 0
#     no_coverage = []
#     failed    = []

#     logger.info(f"[soil] Fetching {len(GLOBAL_LOCATIONS)} cities from WoSIS")
#     logger.info("=" * 50)

#     for i, loc in enumerate(GLOBAL_LOCATIONS, 1):
#         city_name = loc["City"]
#         lat, lon  = loc["Lat"], loc["Lon"]
#         logger.info(f"[{i:2d}/{len(GLOBAL_LOCATIONS)}] {city_name}")

#         try:
#             profiles, box_used = fetch_soil_for_city(city_name, lat, lon)

#             if not profiles:
#                 logger.info(f"  No WoSIS coverage found for {city_name} — leaving NULL")
#                 no_coverage.append(city_name)
#                 row = build_soil_row(city_name, loc["Country"], lat, lon, [], None)
#                 df = pd.DataFrame([row])
#                 df.to_sql("soil", engine, schema="public", if_exists="append", index=False)
#                 continue

#             row = build_soil_row(city_name, loc["Country"], lat, lon, profiles, box_used)
#             df = pd.DataFrame([row])
#             df.to_sql("soil", engine, schema="public", if_exists="append", index=False)

#             ph_display = row["phh2o_0_5cm"] / 10 if row["phh2o_0_5cm"] else "null"
#             logger.info(
#                 f"  Saved | pH: {ph_display} | {len(profiles)} profiles "
#                 f"within {box_used}deg | source: wosis"
#             )
#             succeeded += 1

#         except Exception as e:
#             logger.warning(f"  Failed: {e}")
#             failed.append(city_name)

#         time.sleep(0.3)  # light courtesy delay, WoSIS has no documented rate limit

#     logger.info("\n" + "=" * 50)
#     logger.info(f"  Succeeded:     {succeeded}/{len(GLOBAL_LOCATIONS)}")
#     if no_coverage:
#         logger.info(f"  No coverage:   {len(no_coverage)} — {', '.join(no_coverage)}")
#     if failed:
#         logger.info(f"  Failed (error): {', '.join(failed)}")
#     logger.info("=" * 50)


# if __name__ == "__main__":
#     fetch_soil()
