"""Everything a screen needs about a city: the list, its profile, its plants, its climate, its companions."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Connection

from api.caveats import CAVEATS, NO_RECOMMENDATIONS
from api.db import first, get_connection, rows
from api.routers.deps import Tables, known_city, tables
from api.schemas import (CityContext, CityDetail, CityPlantDetail, CityPlants, CitySummary,
                         Companion, MonthlyClimate)

router = APIRouter(prefix="/cities", tags=["cities"])

HAS_SCORES = "EXISTS (SELECT 1 FROM {scores} s WHERE s.city = a.city)"


def _reasons_by_species(conn: Connection, t: Tables, city: str) -> dict:
    found = rows(conn, f"""
        SELECT species, reason_rank, reason, effect, feature_label, feature_value
        FROM {t.reasons} WHERE city = :city ORDER BY species, reason_rank""", city=city)
    grouped: dict = {}
    for r in found:
        grouped.setdefault(r["species"], []).append({
            "rank": r["reason_rank"], "text": r["reason"], "effect": r["effect"],
            "feature_label": r["feature_label"], "feature_value": r["feature_value"]})
    return grouped


def _city_plants(conn: Connection, t: Tables, city: str, limit: int,
                 functional_group: Optional[str] = None, min_score: float = 0.0) -> List[dict]:
    where, params = ["s.city = :city", "s.suitability_score >= :min_score"], {"city": city, "min_score": min_score}
    if functional_group:
        where.append("LOWER(m.functional_group) = LOWER(:group)")
        params["group"] = functional_group
    plants = rows(conn, f"""
        SELECT s.species, m.common_name, p.family, m.functional_group,
               s.suitability_score, s.rank_in_city, s.observed_nearby, m.observation_count
        FROM {t.scores} s
        JOIN {t.fit} m ON m.city = s.city AND m.species = s.species
        LEFT JOIN {t.profiles} p ON p.species = s.species
        WHERE {' AND '.join(where)}
        ORDER BY s.rank_in_city
        LIMIT :limit""", limit=limit, **params)
    reasons = _reasons_by_species(conn, t, city)
    for plant in plants:
        plant["reasons"] = reasons.get(plant["species"], [])
    return plants


def _city_detail(conn: Connection, t: Tables, city: str) -> dict:
    return first(conn, f"""
        SELECT a.city, a.country, a.latitude, a.longitude, a.frost_zone, a.soil_ph,
               a.clay_pct, a.sand_pct, a.silt_pct, a.organic_carbon_g_kg, a.nitrogen_g_kg,
               a.soil_texture_class, a.ph_band, a.rainfall_band, a.avg_annual_precip_mm,
               a.avg_frost_days_per_year, a.frost_free_days_per_year, a.avg_annual_gdd,
               a.temp_variability_c, a.water_stress_category, a.irrigation_needed_flag,
               a.soil_feature_completeness, a.climate_feature_completeness, a.last_updated_at,
               {HAS_SCORES.format(scores=t.scores)} AS has_recommendations
        FROM {t.annual} a WHERE a.city = :city""", city=city)


@router.get("", response_model=List[CitySummary], summary="All cities")
def list_cities(
    country: Optional[str] = Query(None, description="Two-letter country code, e.g. NG"),
    search: Optional[str] = Query(None, description="Start of a city name, for type-ahead search"),
    has_recommendations: Optional[bool] = Query(None, description="Only cities that do (or do not) have scores"),
    conn: Connection = Depends(get_connection), t: Tables = Depends(tables),
):
    where, params = ["1 = 1"], {}
    if country:
        where.append("UPPER(a.country) = UPPER(:country)")
        params["country"] = country.strip()
    if search:
        where.append("LOWER(a.city) LIKE :search")
        params["search"] = search.strip().lower() + "%"
    if has_recommendations is not None:
        where.append(("" if has_recommendations else "NOT ") + HAS_SCORES.format(scores=t.scores))
    return rows(conn, f"""
        SELECT a.city, a.country, a.latitude, a.longitude, a.frost_zone, a.soil_ph,
               {HAS_SCORES.format(scores=t.scores)} AS has_recommendations
        FROM {t.annual} a WHERE {' AND '.join(where)} ORDER BY a.city""", **params)


@router.get("/{city}", response_model=CityDetail, summary="One city's soil and climate profile")
def city_profile(city: str = Depends(known_city), conn: Connection = Depends(get_connection),
                 t: Tables = Depends(tables)):
    return _city_detail(conn, t, city)


@router.get("/{city}/plants", response_model=CityPlants, summary="Plants ranked for a city, with reasons")
def city_plants(
    city: str = Depends(known_city),
    limit: int = Query(10, ge=1, le=100, description="How many plants to return"),
    functional_group: Optional[str] = Query(None, description="e.g. cereal, legume"),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    conn: Connection = Depends(get_connection), t: Tables = Depends(tables),
):
    plants = _city_plants(conn, t, city, limit, functional_group, min_score)
    available = bool(first(conn, f"SELECT 1 AS found FROM {t.scores} WHERE city = :city", city=city))
    return {"city": city, "recommendations_available": available,
            "message": None if available else NO_RECOMMENDATIONS, "plants": plants}


@router.get("/{city}/plants/{species}", response_model=CityPlantDetail,
            summary="One plant in one city: score, reasons, fit checks and crop needs")
def city_plant_detail(species: str, city: str = Depends(known_city),
                      conn: Connection = Depends(get_connection), t: Tables = Depends(tables)):
    found = first(conn, f"SELECT species FROM {t.scores} WHERE city = :city AND LOWER(species) = LOWER(:s)",
                  city=city, s=species.strip())
    if not found:
        raise HTTPException(status_code=404, detail=f"No score for {species} in {city}")
    row = first(conn, f"""
        SELECT m.months_in_optimal_temp, m.frost_free_months, m.months_to_mature,
               m.enough_warm_months, m.enough_frost_free_months, m.ph_gap, m.trait_fit_share
        FROM {t.fit} m WHERE m.city = :city AND m.species = :s""", city=city, s=found["species"])
    traits = first(conn, f"SELECT * FROM {t.profiles} WHERE species = :s", s=found["species"])
    plant = next(p for p in _city_plants(conn, t, city, limit=1000) if p["species"] == found["species"])
    return {**plant, "fit": row, "traits": traits}


@router.get("/{city}/climate/monthly", response_model=List[MonthlyClimate],
            summary="Average climate for each calendar month (10-year NASA average)")
def city_monthly_climate(city: str = Depends(known_city), conn: Connection = Depends(get_connection),
                         t: Tables = Depends(tables)):
    return rows(conn, f"""
        SELECT month, month_name, avg_temp_c, avg_max_temp_c, avg_min_temp_c, avg_monthly_rain_mm,
               avg_monthly_gdd, avg_frost_days_in_month, is_frost_free_month, is_good_planting_month
        FROM {t.monthly} WHERE city = :city ORDER BY month""", city=city)


@router.get("/{city}/companions", response_model=List[Companion],
            summary="Crops that grow well together near this city")
def city_companions(city: str = Depends(known_city), limit: int = Query(10, ge=1, le=50),
                    conn: Connection = Depends(get_connection), t: Tables = Depends(tables)):
    return rows(conn, f"""
        SELECT pair_rank, species_a, species_b, mechanism, benefit_category, evidence_level,
               relationship_score, notes
        FROM {t.companions} WHERE city = :city ORDER BY pair_rank LIMIT :limit""", city=city, limit=limit)


@router.get("/{city}/context", response_model=CityContext,
            summary="Everything the AI assistant may quote about a city, in one call")
def city_context(city: str = Depends(known_city), conn: Connection = Depends(get_connection),
                 t: Tables = Depends(tables)):
    detail = _city_detail(conn, t, city)
    top = _city_plants(conn, t, city, limit=5)
    companions = rows(conn, f"""
        SELECT pair_rank, species_a, species_b, mechanism, benefit_category, evidence_level,
               relationship_score, notes
        FROM {t.companions} WHERE city = :city ORDER BY pair_rank LIMIT 5""", city=city)
    caveats = list(CAVEATS) if top else [NO_RECOMMENDATIONS]
    return {"city": detail, "recommendations_available": bool(top), "top_plants": top,
            "companions": companions, "caveats": caveats}
