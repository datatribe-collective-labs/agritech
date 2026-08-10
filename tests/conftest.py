"""

PURPOSE:
  Defines "fixtures" — reusable pieces of test setup that any
  test can request just by naming them as a parameter.

"""

import sys
import os

# Add scripts/ to path so tests can import fetch_soil, db_utils, etc.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
import pandas as pd
from unittest.mock import MagicMock


# LOCATION FIXTURES

@pytest.fixture
def sample_locations():
    """
    3-city subset used instead of all 54.
    3 cities = enough to test logic, fast enough to not slow tests.
    Covers Europe, Africa, Asia for regional diversity.
    """
    return [
        {"City": "Paris",   "Country": "FR", "Lat": 48.8566, "Lon":   2.3522},
        {"City": "Nairobi", "Country": "KE", "Lat": -1.2921, "Lon":  36.8219},
        {"City": "Tokyo",   "Country": "JP", "Lat": 35.6762, "Lon": 139.6503},
    ]


# API RESPONSE FIXTURES

@pytest.fixture
def mock_gbif_response():
    """
    One page of GBIF results.
    endOfRecords=True stops the pagination loop after 1 batch.
    """
    return {
        "results": [{
            "species": "Zea mays", "scientificName": "Zea mays L.",
            "kingdom": "Plantae", "phylum": "Tracheophyta",
            "class": "Liliopsida", "order": "Poales",
            "family": "Poaceae", "genus": "Zea",
            "country": "US", "continent": "NORTH_AMERICA",
            "stateProvince": "Iowa", "locality": "Des Moines",
            "decimalLatitude": 41.5868, "decimalLongitude": -93.6250,
            "elevation": 270.0, "year": 2023, "month": 6, "day": 15,
            "eventDate": "2023-06-15", "habitat": "agricultural",
            "occurrenceStatus": "PRESENT", "basisOfRecord": "HUMAN_OBSERVATION",
            "institutionCode": "iNat", "datasetName": "iNaturalist",
            "publisher": "iNaturalist",
            "coordinateUncertaintyInMeters": 10.0,
            "identifiedBy": "John Doe", "recordedBy": "Jane Doe",
        }],
        "endOfRecords": True,  # pagination stops here
        "count": 1,
    }


@pytest.fixture
def mock_soil_response():
    """
    Soil API response for one location.
  
    """
    return {
        "properties": {
            "layers": [
                {"name": "clay",     "depths": [{"label": "0-5cm", "values": {"mean": 250}}]},
                {"name": "sand",     "depths": [{"label": "0-5cm", "values": {"mean": 400}}]},
                {"name": "silt",     "depths": [{"label": "0-5cm", "values": {"mean": 350}}]},
                {"name": "soc",      "depths": [{"label": "0-5cm", "values": {"mean": 180}}]},
                {"name": "phh2o",    "depths": [{"label": "0-5cm", "values": {"mean":  65}}]},
                {"name": "nitrogen", "depths": [{"label": "0-5cm", "values": {"mean": 120}}]},
            ]
        }
    }


@pytest.fixture
def mock_weather_response():
    """
    OpenWeatherMap current weather for one city.
    Nested structure mirrors the real API exactly.
    """
    return {
        "name": "Paris", "sys": {"country": "FR"},
        "coord": {"lat": 48.8566, "lon": 2.3522},
        "main": {
            "temp": 18.5, "feels_like": 17.2,
            "temp_min": 15.0, "temp_max": 21.0,
            "humidity": 65, "pressure": 1013,
        },
        "wind": {"speed": 3.5, "deg": 220},
        "clouds": {"all": 40},
        "weather": [{"main": "Clouds", "description": "scattered clouds"}],
        "visibility": 10000,
    }


@pytest.fixture
def mock_open_meteo_response():
    """
    Open-Meteo 7-day forecast.
    precipitation_sum in mm/day, et0 in mm/day.
    """
    return {
        "daily": {
            "time": ["2026-06-01","2026-06-02","2026-06-03",
                     "2026-06-04","2026-06-05","2026-06-06","2026-06-07"],
            "precipitation_sum":          [0.0, 2.5, 0.0, 1.2, 0.0, 0.0, 3.1],
            "et0_fao_evapotranspiration": [3.5, 2.8, 4.1, 3.2, 4.5, 4.0, 3.8],
        }
    }


@pytest.fixture
def mock_flood_response():
    """
    Open-Meteo flood API — river discharge in m³/s.
    None represents missing model data — our code must handle it.
    """
    return {
        "daily": {
            "river_discharge": [
                1.2, 1.5, 1.3, None, 1.8, 2.1, 1.9,
                1.6, 1.4, 1.7, 1.5, 1.3, 1.2, 1.1, 1.0, 0.9
            ]
        }
    }


@pytest.fixture
def mock_nasa_response():
    """
    NASA POWER API — 3 days of daily climate data.
    -999 is NASA's sentinel for missing data == must become None.
    T2M on 20240103 is -999 to test that conversion.
    """
    return {
        "properties": {
            "parameter": {
                "T2M":               {"20240101":  5.2, "20240102":  6.1, "20240103": -999},
                "T2M_MAX":           {"20240101":  8.5, "20240102":  9.2, "20240103":  7.8},
                "T2M_MIN":           {"20240101":  2.1, "20240102":  3.0, "20240103":  1.5},
                "PRECTOTCORR":       {"20240101":  0.0, "20240102":  2.5, "20240103":  0.0},
                "RH2M":              {"20240101": 72.0, "20240102": 68.0, "20240103": 75.0},
                "WS2M":              {"20240101":  3.2, "20240102":  2.8, "20240103":  4.1},
                "ALLSKY_SFC_SW_DWN": {"20240101":  5.5, "20240102":  4.2, "20240103":  6.1},
                "GWETROOT":          {"20240101": 0.45, "20240102": 0.48, "20240103": 0.42},
            }
        }
    }


# DATABASE FIXTURES

@pytest.fixture
def mock_engine():
    """
    Fake SQLAlchemy engine using MagicMock.
    MagicMock accepts any method call without crashing
    and records calls so we can assert they happened.
    df.to_sql(engine=mock_engine) won't touch Postgres.
    """
    engine = MagicMock()
    # Make connect() work as a context manager (with engine.connect() as conn)
    engine.connect.return_value.__enter__ = MagicMock(return_value=MagicMock())
    engine.connect.return_value.__exit__  = MagicMock(return_value=False)
    return engine


# DATAFRAME FIXTURES

@pytest.fixture
def sample_soil_df():
    """Clean soil row — what fetch_soil() produces after parsing."""
    return pd.DataFrame([{
        "city": "Paris", "country": "FR",
        "latitude": 48.8566, "longitude": 2.3522,
        "clay_0_5cm": 250, "sand_0_5cm": 400, "silt_0_5cm": 350,
        "soc_0_5cm": 180, "phh2o_0_5cm": 65, "nitrogen_0_5cm": 120,
    }])


@pytest.fixture
def sample_weather_df():
    """Clean weather row — what fetch_weather() produces."""
    return pd.DataFrame([{
        "city": "Paris", "country": "FR",
        "latitude": 48.8566, "longitude": 2.3522,
        "temperature_c": 18.5, "feels_like_c": 17.2,
        "min_temp_c": 15.0, "max_temp_c": 21.0,
        "humidity_pct": 65, "pressure_hpa": 1013,
        "ground_pressure_hpa": None,
        "wind_speed_mps": 3.5, "wind_direction_deg": 220,
        "cloud_cover_pct": 40, "weather_main": "Clouds",
        "description": "scattered clouds", "visibility_m": 10000,
    }])


@pytest.fixture
def sample_water_df():
    """Clean water row — what fetch_water() produces."""
    return pd.DataFrame([{
        "city": "Paris", "country": "FR",
        "latitude": 48.8566, "longitude": 2.3522,
        "avg_daily_precip_mm": 0.97, "avg_daily_et0_mm": 3.70,
        "avg_daily_water_deficit_mm": 2.73,
        "forecast_start_date": "2026-06-01",
        "forecast_end_date":   "2026-06-07",
        "avg_river_discharge_m3s": 1.45,
        "max_river_discharge_m3s": 2.10,
    }])