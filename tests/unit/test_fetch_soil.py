"""
What matters for the WoSIS soil fetch:
  - The search widens when a property (pH) has no measurement in the small box,
    not only when the small box has no profiles at all.
  - Each property comes from the closest box that has a value for it.
  - A property with no measurement anywhere stays empty (never filled with a guess).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import fetch_soil  # noqa: E402

LAT, LON = 52.52, 13.40


def profile(lat, lon, ph=None, clay=30.0):
    """A WoSIS profile with one layer. Properties given as None have no measurement."""
    def val(v):
        return [] if v is None else [{"value": [str(v)], "valueAvg": v}]
    return {
        "profileId": 1, "latitude": lat, "longitude": lon,
        "layers": [{
            "upperDepth": 0, "lowerDepth": 5,
            "phaqValues": val(ph), "clayValues": val(clay), "sandValues": val(40.0),
            "siltValues": val(30.0), "orgcValues": val(12.0), "nitkjdValues": val(1.2),
        }],
    }


def fake_query(small, large):
    """Returns a stand-in for query_wosis_box giving `small` for 0.5 deg and `large` for 2.0 deg."""
    def query(lat, lon, box_deg):
        return small if box_deg == 0.5 else large
    return query


def test_widens_when_small_box_has_profiles_but_no_ph(monkeypatch):
    near = [profile(52.5, 13.4, ph=None)]
    far = [profile(52.0, 14.0, ph=6.4)]
    monkeypatch.setattr(fetch_soil, "query_wosis_box", fake_query(near, far))

    levels = fetch_soil.fetch_soil_for_city("Berlin", LAT, LON)
    row = fetch_soil.build_soil_row("Berlin", "DE", LAT, LON, levels)

    assert [box for box, _ in levels] == [0.5, 2.0]
    assert row["phh2o_0_5cm"] == 64          # pH 6.4 stored x10, from the wider box
    assert row["wosis_box_degrees_used"] == 2.0
    assert row["wosis_ph_n_profiles"] == 1


def test_does_not_widen_when_everything_is_present(monkeypatch):
    near = [profile(52.5, 13.4, ph=7.0)]
    calls = []

    def query(lat, lon, box_deg):
        calls.append(box_deg)
        return near

    monkeypatch.setattr(fetch_soil, "query_wosis_box", query)
    levels = fetch_soil.fetch_soil_for_city("Berlin", LAT, LON)
    row = fetch_soil.build_soil_row("Berlin", "DE", LAT, LON, levels)

    assert calls == [0.5]
    assert row["phh2o_0_5cm"] == 70


def test_close_values_win_over_wider_box_values(monkeypatch):
    near = [profile(52.5, 13.4, ph=None, clay=20.0)]
    far = [profile(52.0, 14.0, ph=6.4, clay=50.0)]
    monkeypatch.setattr(fetch_soil, "query_wosis_box", fake_query(near, far))

    levels = fetch_soil.fetch_soil_for_city("Berlin", LAT, LON)
    row = fetch_soil.build_soil_row("Berlin", "DE", LAT, LON, levels)

    assert row["clay_0_5cm"] == 200          # clay 20 % from the CLOSE box, not 50 % from the wide one


def test_property_missing_everywhere_stays_empty(monkeypatch):
    monkeypatch.setattr(
        fetch_soil, "query_wosis_box",
        fake_query([profile(52.5, 13.4, ph=None)], [profile(52.0, 14.0, ph=None)]))

    levels = fetch_soil.fetch_soil_for_city("Berlin", LAT, LON)
    row = fetch_soil.build_soil_row("Berlin", "DE", LAT, LON, levels)

    assert row["phh2o_0_5cm"] is None
    assert row["wosis_ph_n_profiles"] == 0


def test_no_profiles_at_all_gives_empty_row(monkeypatch):
    monkeypatch.setattr(fetch_soil, "query_wosis_box", fake_query([], []))
    levels = fetch_soil.fetch_soil_for_city("Nowhere", 0.0, 0.0)
    row = fetch_soil.build_soil_row("Nowhere", "XX", 0.0, 0.0, levels)

    assert levels == []
    assert row["phh2o_0_5cm"] is None and row["clay_0_5cm"] is None
    assert row["wosis_box_degrees_used"] is None
