"""Plain statements the app shows next to any recommendation, kept in one place so the wording is reviewed once."""

CAVEATS = [
    "A score says how much a crop looks like the crops people recorded near this city. "
    "It is not a yield forecast.",
    "Recorded means someone logged the crop on GBIF within 100 km. A crop nobody logged "
    "can still grow well.",
    "The reasons describe how the model scored the crop, not proof of what makes it grow.",
    "Some crop requirements come from a general agronomic reference that has not been checked "
    "against a paper yet; each crop shows its source.",
]

NO_RECOMMENDATIONS = (
    "No crop has been recorded within 100 km of this city, so there is no local record to compare "
    "against and no recommendation is shown."
)

NO_SOIL_DATA = (
    "This city has no soil pH measurement in the soil database (WoSIS), so crops cannot be checked "
    "against its soil and no recommendation is shown."
)
