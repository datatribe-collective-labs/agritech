"""Response shapes. Field names match the dbt marts so a stakeholder can trace any value back."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class Reason(BaseModel):
    rank: int
    text: str
    effect: str                      # 'raises' or 'lowers'
    feature_label: str
    feature_value: Optional[float] = None


class CitySummary(BaseModel):
    city: str
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    frost_zone: Optional[str] = None
    soil_ph: Optional[float] = None
    has_recommendations: bool        # False: no crop recorded within 100 km, so no score


class CityDetail(CitySummary):
    clay_pct: Optional[float] = None
    sand_pct: Optional[float] = None
    silt_pct: Optional[float] = None
    organic_carbon_g_kg: Optional[float] = None
    nitrogen_g_kg: Optional[float] = None
    soil_texture_class: Optional[str] = None
    ph_band: Optional[str] = None
    rainfall_band: Optional[str] = None
    avg_annual_precip_mm: Optional[float] = None
    avg_frost_days_per_year: Optional[float] = None
    frost_free_days_per_year: Optional[float] = None
    avg_annual_gdd: Optional[float] = None
    temp_variability_c: Optional[float] = None
    water_stress_category: Optional[str] = None
    irrigation_needed_flag: Optional[int] = None
    soil_feature_completeness: Optional[int] = None    # 0 to 6
    climate_feature_completeness: Optional[int] = None  # 0 to 5
    last_updated_at: Optional[datetime] = None


class MonthlyClimate(BaseModel):
    month: int
    month_name: Optional[str] = None
    avg_temp_c: Optional[float] = None
    avg_max_temp_c: Optional[float] = None
    avg_min_temp_c: Optional[float] = None
    avg_monthly_rain_mm: Optional[float] = None
    avg_monthly_gdd: Optional[float] = None
    avg_frost_days_in_month: Optional[float] = None
    is_frost_free_month: Optional[bool] = None
    is_good_planting_month: Optional[bool] = None


class PlantSummary(BaseModel):
    species: str
    common_name: Optional[str] = None
    family: Optional[str] = None
    functional_group: Optional[str] = None


class PlantProfile(PlantSummary):
    growth_habit: Optional[str] = None
    root_depth_class: Optional[str] = None
    nitrogen_role: Optional[str] = None
    nitrogen_fixation: Optional[bool] = None
    drought_tolerance: Optional[str] = None
    shade_tolerance: Optional[str] = None
    water_demand: Optional[str] = None
    frost_hardy: Optional[bool] = None
    optimal_ph_min: Optional[float] = None
    optimal_ph_max: Optional[float] = None
    optimal_temp_min_c: Optional[float] = None
    optimal_temp_max_c: Optional[float] = None
    days_to_maturity_min: Optional[int] = None
    days_to_maturity_max: Optional[int] = None
    notes: Optional[str] = None
    trait_source: Optional[str] = None
    source_url: Optional[str] = None


class FitChecks(BaseModel):
    """What the crop needs versus what the city offers (plain arithmetic, see mart_species_city_suitability)."""
    months_in_optimal_temp: Optional[int] = None
    frost_free_months: Optional[int] = None
    months_to_mature: Optional[int] = None
    enough_warm_months: Optional[int] = None
    enough_frost_free_months: Optional[int] = None
    ph_gap: Optional[float] = None
    trait_fit_share: Optional[float] = None


class CityPlant(PlantSummary):
    suitability_score: float          # 0 to 1, from cities the model had not seen
    rank_in_city: int                 # 1 = best in this city
    observed_nearby: bool             # recorded by GBIF within 100 km
    observation_count: Optional[int] = None
    reasons: List[Reason] = []


class CityPlants(BaseModel):
    city: str
    recommendations_available: bool
    message: Optional[str] = None
    plants: List[CityPlant]


class CityPlantDetail(CityPlant):
    fit: FitChecks
    traits: PlantProfile


class PlantCity(BaseModel):
    city: str
    country: Optional[str] = None
    suitability_score: float
    rank_in_city: int                 # this crop's rank among all crops in the city
    observed_nearby: bool


class Companion(BaseModel):
    pair_rank: int
    species_a: str
    species_b: str
    mechanism: Optional[str] = None
    benefit_category: Optional[str] = None
    evidence_level: Optional[str] = None
    relationship_score: Optional[int] = None
    relationship: Optional[str] = None
    notes: Optional[str] = None
    evidence_source: Optional[str] = None
    source_url: Optional[str] = None


class PlantCompanion(BaseModel):
    """The partner of one crop in one city, with the reason the pair works."""
    partner: str
    partner_common_name: Optional[str] = None
    partner_functional_group: Optional[str] = None
    partner_rank_in_city: Optional[int] = None   # empty when the partner has no score in this city
    relationship: Optional[str] = None
    mechanism: Optional[str] = None
    benefit_category: Optional[str] = None
    evidence_level: Optional[str] = None
    relationship_score: Optional[int] = None
    notes: Optional[str] = None
    evidence_source: Optional[str] = None
    source_url: Optional[str] = None


class CityContext(BaseModel):
    """One bundle with everything the AI layer may quote about a city (and nothing else)."""
    city: CityDetail
    recommendations_available: bool
    top_plants: List[CityPlant]
    companions: List[Companion]
    caveats: List[str]


class TrainingRun(BaseModel):
    """One retraining attempt: what was tested, and whether the model was allowed to go live."""
    run_id: str
    trained_at: Optional[str] = None
    status: str                                   # "accepted" (went live) or "rejected"
    rejected_because: Optional[str] = None
    model_auc: Optional[float] = None
    best_baseline: Optional[str] = None
    gain_over_baseline_auc: Optional[float] = None
    gain_range_low: Optional[float] = None
    gain_range_high: Optional[float] = None
    top_n_hit_rate: Optional[float] = None
    cities: Optional[int] = None
    rows_used: Optional[int] = None


class ModelInfo(BaseModel):
    verdict: Optional[str] = None
    trained_at: Optional[str] = None
    rows: Optional[int] = None
    cities: Optional[int] = None
    share_recorded: Optional[float] = None
    model: Optional[dict] = None
    best_baseline: Optional[str] = None
    gain_95_percent_range: Optional[List[float]] = None
    caveats: List[str]
