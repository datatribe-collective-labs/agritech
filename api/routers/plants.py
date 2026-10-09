"""The crop catalogue and, for each crop, the cities where it scores best."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from api.db import get_connection, rows, first
from api.routers.deps import Tables, known_species, tables
from api.schemas import PlantCity, PlantProfile, PlantSummary

router = APIRouter(prefix="/plants", tags=["plants"])


@router.get("", response_model=List[PlantSummary], summary="All crops")
def list_plants(
    search: Optional[str] = Query(None, description="Part of a common or scientific name"),
    functional_group: Optional[str] = Query(None, description="e.g. cereal, legume"),
    conn: Connection = Depends(get_connection), t: Tables = Depends(tables),
):
    where, params = ["1 = 1"], {}
    if search:
        where.append("(LOWER(species) LIKE :search OR LOWER(common_name) LIKE :search)")
        params["search"] = "%" + search.strip().lower() + "%"
    if functional_group:
        where.append("LOWER(functional_group) = LOWER(:group)")
        params["group"] = functional_group.strip()
    return rows(conn, f"""
        SELECT species, common_name, family, functional_group
        FROM {t.profiles} WHERE {' AND '.join(where)} ORDER BY common_name, species""", **params)


@router.get("/{species}", response_model=PlantProfile, summary="What one crop needs")
def plant_profile(species: str = Depends(known_species), conn: Connection = Depends(get_connection),
                  t: Tables = Depends(tables)):
    return first(conn, f"SELECT * FROM {t.profiles} WHERE species = :s", s=species)


@router.get("/{species}/cities", response_model=List[PlantCity], summary="Cities where this crop scores highest")
def plant_cities(species: str = Depends(known_species), limit: int = Query(10, ge=1, le=100),
                 conn: Connection = Depends(get_connection), t: Tables = Depends(tables)):
    return rows(conn, f"""
        SELECT s.city, a.country, s.suitability_score, s.rank_in_city, s.observed_nearby
        FROM {t.scores} s JOIN {t.annual} a ON a.city = s.city
        WHERE s.species = :s ORDER BY s.suitability_score DESC, s.city LIMIT :limit""", s=species, limit=limit)
