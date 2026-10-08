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


_next_id = iter(range(1, 10_000))


def profile(lat, lon, ph=None, clay=30.0):
    """A WoSIS profile with one layer. Properties given as None have no measurement."""
    def val(v):
        return [] if v is None else [{"value": [str(v)], "valueAvg": v}]
    return {
        "profileId": next(_next_id), "latitude": lat, "longitude": lon,
        "layers": [{
            "upperDepth": 0, "lowerDepth": 5,
            "phaqValues": val(ph), "clayValues": val(clay), "sandValues": val(40.0),
            "siltValues": val(30.0), "orgcValues": val(12.0), "nitkjdValues": val(1.2),
        }],
    }


def fake_query(small, large):
    """
    Stand-in for query_wosis_box: `small` for the near box centred on the city,
    `large` for the one tile east of the city, nothing for the other tiles.
    """
    def query(lat, lon, half_width):
        if lat == LAT and lon == LON and half_width == fetch_soil.NEAR_BOX_DEG:
            return small
        if abs(lat - LAT) < 1e-9 and abs(lon - (LON + 1.0)) < 1e-9:
            return large
        return []
    return query


def test_widens_when_small_box_has_profiles_but_no_ph(monkeypatch):
    near = [profile(52.5, 13.4, ph=None)]
    far = [profile(52.0, 14.0, ph=6.4)]
    monkeypatch.setattr(fetch_soil, "query_wosis_box", fake_query(near, far))

    levels = fetch_soil.fetch_soil_for_city("Berlin", LAT, LON)
    row = fetch_soil.build_soil_row("Berlin", "DE", LAT, LON, levels)

    assert [box for box, _ in levels] == [0.5, fetch_soil.WIDE_REACH_DEG]
    assert row["phh2o_0_5cm"] == 64          # pH 6.4 stored x10, from the wider box
    assert row["wosis_box_degrees_used"] == fetch_soil.WIDE_REACH_DEG
    assert row["wosis_ph_n_profiles"] == 1


def test_does_not_widen_when_everything_is_present(monkeypatch):
    near = [profile(52.5, 13.4, ph=7.0)]
    calls = []

    def query(lat, lon, half_width):
        calls.append(half_width)
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


def test_tiles_find_ph_that_one_big_box_would_miss(monkeypatch):
    """The near box has profiles without pH; pH sits in two different neighbouring tiles."""
    near = [profile(52.5, 13.4, ph=None)]
    east = [profile(52.5, 14.4, ph=6.0)]
    north = [profile(53.5, 13.4, ph=7.0)]

    def query(lat, lon, half_width):
        if lat == LAT and lon == LON:
            return near
        if abs(lat - LAT) < 1e-9 and abs(lon - (LON + 1.0)) < 1e-9:
            return east
        if abs(lat - (LAT + 1.0)) < 1e-9 and abs(lon - LON) < 1e-9:
            return north
        return []

    monkeypatch.setattr(fetch_soil, "query_wosis_box", query)
    levels = fetch_soil.fetch_soil_for_city("Berlin", LAT, LON)
    row = fetch_soil.build_soil_row("Berlin", "DE", LAT, LON, levels)

    assert row["wosis_ph_n_profiles"] == 2
    assert 60 < row["phh2o_0_5cm"] < 70      # between 6.0 and 7.0, stored x10


def test_same_profile_in_two_tiles_is_counted_once(monkeypatch):
    shared = profile(52.5, 13.9, ph=6.0)
    monkeypatch.setattr(
        fetch_soil, "query_wosis_box",
        lambda lat, lon, half_width: [] if (lat, lon) == (LAT, LON) else [shared])
    levels = fetch_soil.fetch_soil_for_city("Berlin", LAT, LON)
    row = fetch_soil.build_soil_row("Berlin", "DE", LAT, LON, levels)
    assert row["wosis_ph_n_profiles"] == 1
