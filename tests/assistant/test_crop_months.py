"""Tests for month names and the city soil pH on the pinned card. Numbers in these tests are made up for the test."""

# Function under test.
from assistant.memory.crop_months import months_suited
# The output check that blocks numbers not in the data.
from assistant.guardrails.output_rails import check_output
# The model's standing rules.
from assistant.agent.prompts import SYSTEM_PROMPT


def _year() -> list:
    """Twelve made-up months: warm from March to October, frost in January and December."""
    # Names for the twelve months.
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # Made-up average temperatures.
    temps = [4, 6, 12, 16, 20, 24, 26, 25, 21, 15, 9, 5]
    # One row per month, with frost only when it is below 5 degrees.
    return [{"month": i + 1, "month_name": n, "avg_temp_c": t, "is_frost_free_month": t >= 5}
            # Pair each name with its temperature.
            for i, (n, t) in enumerate(zip(names, temps))]


# A made-up crop that likes 15 to 27 degrees.
TRAITS = {"optimal_temp_min_c": 15, "optimal_temp_max_c": 27}


def test_names_the_months_inside_the_ideal_range():
    """Months between 15 and 27 degrees are named, and 'both' also needs no frost."""
    # Counts the app would report for the made-up year: 7 warm months (Apr to Oct), 11 frost-free (all but Jan).
    fit = {"months_in_optimal_temp": 7, "frost_free_months": 11}
    # Work out the names.
    result = months_suited(_year(), TRAITS, fit)
    # Exactly the months inside the temperature range.
    assert result["temperature_suits"] == ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    # Every one of those months is also frost free, so 'both' is the same list.
    assert result["both"] == result["temperature_suits"]
    # January is the only month with frost.
    assert "Jan" not in result["frost_free"] and len(result["frost_free"]) == 11


def test_count_mismatch_means_no_names():
    """If our count disagrees with the app's own count, say nothing rather than contradict the page."""
    # The app says 9 months, our rule finds a different number.
    assert months_suited(_year(), TRAITS, {"months_in_optimal_temp": 9}) is None


def test_unknown_temperature_range_means_no_names():
    """A crop without a known ideal range cannot be named."""
    # No range.
    assert months_suited(_year(), {"optimal_temp_min_c": None, "optimal_temp_max_c": None}, {}) is None
    # No monthly data.
    assert months_suited([], TRAITS, {}) is None


def test_missing_month_name_falls_back_to_the_number():
    """Rows without a month name still get one."""
    # One row without a name.
    rows = [{"month": 3, "month_name": None, "avg_temp_c": 20, "is_frost_free_month": True}]
    # March is named from its number.
    assert months_suited(rows, TRAITS, {})["temperature_suits"] == ["Mar"]


def test_card_carries_soil_ph_and_honest_months(service, visitor):
    """On the sample data the card has the city's soil pH, and no months (the sample crop has no temperature range)."""
    # Open a crop chat.
    _, card = service.start_session(visitor, "Lagos", "Zea mays")
    # The sample city's soil pH.
    assert card["city_soil_ph"] == 5.9
    # No temperature range for this crop, so no month names are invented.
    assert card["months_suited"] is None


def test_soil_ph_question_is_answered_from_the_card(service, visitor):
    """'What is the soil pH here?' states the app's own value and passes every output check."""
    # Open a crop chat.
    session_id, _ = service.start_session(visitor, "Lagos", "Zea mays")
    # Ask for the soil pH.
    answer = service.ask(visitor, session_id, "What is the soil pH here?")
    # Quoted from the card, and not sent to review.
    assert "5.9" in answer.text and not answer.needs_review


def test_a_number_from_the_farmer_is_still_blocked():
    """Repeating a figure that is not in the data is flagged, which is why the prompt forbids it."""
    # Facts hold only the app's own pH.
    facts = [{"city_soil_ph": 5.9}]
    # An answer that repeats the farmer's 8.6.
    problems = check_output("You said the pH was 8.6.", facts, set())
    # It is flagged.
    assert any("8.6" in p for p in problems)
    # And the model is told not to do it.
    assert "Never repeat a number the farmer typed" in SYSTEM_PROMPT
