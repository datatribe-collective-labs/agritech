"""Load test for the Planting Intelligence API: many farmers browsing at the same time."""

# Read settings from the environment.
import os
# Pick random cities and crops.
import random

# Locust drives the simulated users.
from locust import HttpUser, between, events, task

# Cities and crops are loaded once from the live API, so we only ask for things that exist.
CITIES: list = []
# Crops that actually have a score in each city.
CROPS: dict = {}


@events.test_start.add_listener
def load_names(environment, **_):
    """Fetch real city and crop names before the users start."""
    # A plain HTTP client for the setup calls.
    import requests
    # The host being tested, e.g. https://94-237-15-238.sslip.io
    host = environment.host
    # Take the first 40 cities so the test is repeatable.
    for city in requests.get(f"{host}/cities", timeout=30).json()[:40]:
        # Keep the city name.
        name = city["city"]
        # Ask for its top crops.
        plants = requests.get(f"{host}/cities/{name}/plants?limit=10", timeout=30).json()
        # Remember the city only if it has crops.
        if plants.get("plants"):
            # Store the city.
            CITIES.append(name)
            # Store its crops.
            CROPS[name] = [p["species"] for p in plants["plants"]]


class Farmer(HttpUser):
    """One person using the website: look up a city, open a crop, check the months."""

    # A real person pauses 1 to 4 seconds between clicks.
    wait_time = between(1, 4)

    @task(5)
    def city_page(self):
        """The most common visit: a city and its ranked crops."""
        # Pick a city.
        city = random.choice(CITIES)
        # The city profile.
        self.client.get(f"/cities/{city}", name="/cities/{city}")
        # Its ranked crops.
        self.client.get(f"/cities/{city}/plants?limit=10", name="/cities/{city}/plants")

    @task(3)
    def crop_page(self):
        """Open one crop in one city, with its companions and months."""
        # Pick a city and one of its crops.
        city = random.choice(CITIES)
        crop = random.choice(CROPS[city])
        # The crop card.
        self.client.get(f"/cities/{city}/plants/{crop}", name="/cities/{city}/plants/{crop}")
        # Its monthly climate.
        self.client.get(f"/cities/{city}/climate/monthly", name="/cities/{city}/climate/monthly")

    @task(1)
    def home(self):
        """The front page lists the cities."""
        # All cities.
        self.client.get("/cities", name="/cities")

    @task(1)
    def health(self):
        """A health check, as a monitor would send."""
        # Is the API and the database up.
        self.client.get("/health")
