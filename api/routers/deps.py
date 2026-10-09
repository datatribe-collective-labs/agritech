"""Helpers shared by the routers."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.engine import Connection

from api.db import first, get_connection, table


def tables(request: Request) -> "Tables":
    return Tables(request.app.state.schema)


class Tables:
    """Schema-qualified names of the mart tables the API reads."""

    def __init__(self, schema: str):
        self.annual = table("mart_ml_annual_features", schema)
        self.monthly = table("mart_planting_features", schema)
        self.fit = table("mart_species_city_suitability", schema)
        self.profiles = table("mart_plant_profiles", schema)
        self.companions = table("mart_city_companions", schema)
        self.scores = table("ml_species_city_suitability", schema)
        self.reasons = table("ml_species_city_explanations", schema)
        self.runs = table("ml_training_runs", schema)


def known_city(city: str, conn: Connection = Depends(get_connection), t: Tables = Depends(tables)) -> str:
    """The city's stored spelling, whatever the capitals in the URL. 404 if it is not one of ours."""
    found = first(conn, f"SELECT city FROM {t.annual} WHERE LOWER(city) = LOWER(:city)", city=city.strip())
    if not found:
        raise HTTPException(status_code=404, detail=f"Unknown city: {city}")
    return found["city"]


def known_species(species: str, conn: Connection = Depends(get_connection), t: Tables = Depends(tables)) -> str:
    found = first(conn, f"SELECT species FROM {t.profiles} WHERE LOWER(species) = LOWER(:s)", s=species.strip())
    if not found:
        raise HTTPException(status_code=404, detail=f"Unknown plant: {species}")
    return found["species"]
