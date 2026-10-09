// The shapes the API returns (see api/schemas.py). Missing values arrive as null, never guessed.

export type CitySummary = {
  city: string;
  country: string | null;
  latitude: number | null;
  longitude: number | null;
  frost_zone: string | null;
  soil_ph: number | null;
  has_recommendations: boolean;
};

export type CityDetail = CitySummary & {
  clay_pct: number | null;
  soil_texture_class: string | null;
  ph_band: string | null;
  rainfall_band: string | null;
  avg_annual_precip_mm: number | null;
  avg_frost_days_per_year: number | null;
};

export type MonthlyClimate = {
  month: number;
  avg_temp_c: number | null;
  avg_monthly_rain_mm: number | null;
  is_good_planting_month: boolean | null;
};

export type Reason = { rank: number; text: string; effect: string };

export type CityPlant = {
  species: string;
  common_name: string | null;
  family: string | null;
  functional_group: string | null;
  suitability_score: number;
  rank_in_city: number;
  observed_nearby: boolean;
  reasons: Reason[];
};

export type CityPlants = {
  city: string;
  recommendations_available: boolean;
  message: string | null;
  plants: CityPlant[];
};

export type FitChecks = {
  months_in_optimal_temp: number | null;
  frost_free_months: number | null;
  months_to_mature: number | null;
  enough_warm_months: number | null;
  enough_frost_free_months: number | null;
  ph_gap: number | null;
  trait_fit_share: number | null;
};

export type PlantProfile = {
  species: string;
  common_name: string | null;
  functional_group: string | null;
  nitrogen_role: string | null;
  drought_tolerance: string | null;
  water_demand: string | null;
  frost_hardy: boolean | null;
  optimal_ph_min: number | null;
  optimal_ph_max: number | null;
  optimal_temp_min_c: number | null;
  optimal_temp_max_c: number | null;
  days_to_maturity_min: number | null;
  days_to_maturity_max: number | null;
  notes: string | null;
  trait_source: string | null;
  source_url: string | null;
};

export type CityPlantDetail = CityPlant & { fit: FitChecks; traits: PlantProfile };

export type PlantCompanion = {
  partner: string;
  partner_common_name: string | null;
  partner_rank_in_city: number | null;
  relationship: string | null;
  mechanism: string | null;
  evidence_level: string | null;
  notes: string | null;
  evidence_source: string | null;
  source_url: string | null;
};

export type ModelInfo = {
  verdict: string | null;
  rows: number | null;
  cities: number | null;
  share_recorded: number | null;
  caveats: string[];
};
