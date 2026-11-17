"""Month names for a crop in a city, worked out from data the app already has.

The app's own count ("9 months a year are in the crop's ideal temperature range") is the number of months whose
average temperature sits inside the crop's ideal range. This file applies the same rule to name those months.
It is plain arithmetic on read-only API data, so nothing is guessed.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Month names to fall back on when the API row has no name.
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _name(row: dict) -> str:
    """The month's name, from the row or from its number."""
    # Prefer the name the API sent.
    if row.get("month_name"):
        # Use it as is.
        return row["month_name"]
    # Otherwise look the name up by month number (1 to 12).
    return MONTH_NAMES[int(row["month"]) - 1]


def months_suited(monthly, traits, fit):
    """Return {'temperature_suits': [...], 'frost_free': [...], 'both': [...]} or None when it cannot be worked out.

    None is returned when the crop has no known ideal temperature range, when there is no monthly data, or when our
    count disagrees with the app's own count (then showing names could contradict the page).
    """
    # Without monthly rows there is nothing to name.
    if not monthly:
        # Cannot work it out.
        return None
    # The crop's ideal temperature range (None when the app does not know it).
    low, high = (traits or {}).get("optimal_temp_min_c"), (traits or {}).get("optimal_temp_max_c")
    # Without a range we cannot say which months suit the crop.
    if low is None or high is None:
        # Cannot work it out.
        return None
    # Months whose average temperature is inside the ideal range (same rule as the app's own count).
    warm = [_name(r) for r in monthly if r.get("avg_temp_c") is not None and low <= r["avg_temp_c"] <= high]
    # The app's own count of such months.
    expected = (fit or {}).get("months_in_optimal_temp")
    # If the two counts differ, say nothing rather than contradict the page.
    if expected is not None and len(warm) != expected:
        # Cannot be trusted.
        return None
    # Months without frost.
    frost_free = [_name(r) for r in monthly if r.get("is_frost_free_month")]
    # The app's own count of frost-free months.
    expected_frost = (fit or {}).get("frost_free_months")
    # Drop the frost list (not the whole result) when its count disagrees.
    if expected_frost is not None and len(frost_free) != expected_frost:
        # Keep only the temperature months.
        return {"temperature_suits": warm}
    # Months that are both warm enough and frost free, in calendar order.
    both = [m for m in warm if m in frost_free]
    # Everything the answer may quote.
    return {"temperature_suits": warm, "frost_free": frost_free, "both": both}
