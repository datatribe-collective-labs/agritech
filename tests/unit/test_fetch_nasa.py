"""
CRITICAL THINGS TO TEST FOR NASA DATA INGESTION:
  - NASA's -999 sentinel value must become None
  - Date format YYYYMMDD must be parsed to YYYY-MM-DD
  - Each date produces one row in the output
  - Empty API responses are handled gracefully
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))


class TestNASAParsing:

    def test_converts_sentinel_minus999_to_none(self, mock_nasa_response):
        """
        NASA uses -999 to mean 'no data available'.
        If we store -999 in the database, the ML model treats it
        as an actual temperature of -999°C — completely wrong.
        Must be converted to None (NULL in SQL).

        Our fixture has T2M = -999 on 20240103 - test that it becomes None.
        """
        from fetch_nasa_power import fetch_nasa_location

        loc = {"City": "Paris", "Country": "FR", "Lat": 48.8566, "Lon": 2.3522}

        with patch("fetch_nasa_power.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_nasa_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            rows = fetch_nasa_location(loc)

        # Find the row for date 2024-01-03
        row_jan3 = next((r for r in rows if r["date"] == "2024-01-03"), None)
        assert row_jan3 is not None, "Row for 2024-01-03 not found"
        assert row_jan3["t2m"] is None, \
            f"Expected None for -999 sentinel, got {row_jan3['t2m']}"

    def test_valid_values_are_preserved(self, mock_nasa_response):
        """
        Non-sentinel values must be stored as-is.
        T2M on 20240101 = 5.2 in fixture — must stay 5.2.
        """
        from fetch_nasa_power import fetch_nasa_location

        loc = {"City": "Paris", "Country": "FR", "Lat": 48.8566, "Lon": 2.3522}

        with patch("fetch_nasa_power.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_nasa_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            rows = fetch_nasa_location(loc)

        row_jan1 = next((r for r in rows if r["date"] == "2024-01-01"), None)
        assert row_jan1 is not None
        assert row_jan1["t2m"] == 5.2

    def test_date_format_is_correct(self, mock_nasa_response):
        """
        NASA sends dates as YYYYMMDD (e.g. '20240101').
        Our database expects YYYY-MM-DD (e.g. '2024-01-01').
        This tests that the conversion is applied.
        """
        from fetch_nasa_power import fetch_nasa_location

        loc = {"City": "Paris", "Country": "FR", "Lat": 48.8566, "Lon": 2.3522}

        with patch("fetch_nasa_power.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_nasa_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            rows = fetch_nasa_location(loc)

        # Every row date must match YYYY-MM-DD format
        for row in rows:
            parts = row["date"].split("-")
            assert len(parts) == 3,            f"Date not in YYYY-MM-DD: {row['date']}"
            assert len(parts[0]) == 4,         f"Year part wrong: {parts[0]}"
            assert len(parts[1]) == 2,         f"Month part wrong: {parts[1]}"
            assert len(parts[2]) == 2,         f"Day part wrong: {parts[2]}"

    def test_one_row_per_date(self, mock_nasa_response):
        """
        Each date in the NASA response must produce exactly one row.
        Our fixture has 3 dates → expect 3 rows.
        """
        from fetch_nasa_power import fetch_nasa_location

        loc = {"City": "Paris", "Country": "FR", "Lat": 48.8566, "Lon": 2.3522}

        with patch("fetch_nasa_power.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_nasa_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            rows = fetch_nasa_location(loc)

        assert len(rows) == 3, f"Expected 3 rows (one per date), got {len(rows)}"

    def test_returns_empty_list_on_api_failure(self):
        """
        API failure must return [] not crash.
        The batch save logic skips empty lists gracefully.
        """
        from fetch_nasa_power import fetch_nasa_location

        loc = {"City": "Paris", "Country": "FR", "Lat": 48.8566, "Lon": 2.3522}

        with patch("fetch_nasa_power.requests.get") as mock_get:
            mock_get.side_effect = Exception("NASA API down")
            rows = fetch_nasa_location(loc)

        assert rows == [], f"Expected empty list on failure, got {rows}"

    def test_all_parameters_present_in_row(self, mock_nasa_response):
        """
        Every row must have all 8 climate parameters.
        Missing parameters create NaN columns that break ML models.
        """
        from fetch_nasa_power import fetch_nasa_location

        loc = {"City": "Paris", "Country": "FR", "Lat": 48.8566, "Lon": 2.3522}

        with patch("fetch_nasa_power.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_nasa_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            rows = fetch_nasa_location(loc)

        expected_params = {
            "t2m", "t2m_max", "t2m_min", "prectotcorr",
            "rh2m", "ws2m", "allsky_sfc_sw_dwn", "gwetroot"
        }

        for row in rows:
            present = set(row.keys())
            missing = expected_params - present
            assert not missing, f"Row missing parameters: {missing}"